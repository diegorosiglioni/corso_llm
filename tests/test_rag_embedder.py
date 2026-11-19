"""Embeddings from LM Studio in batches, model check on /v1/models, and the fake embedder."""

from types import SimpleNamespace

import httpx
import httpx2
import openai
import pytest

from conftest import FakeEmbedder, lm_studio_error
from rag.config import load_config
from rag.embedder import EmbeddingError, LMStudioEmbedder, check_embedding_model, create_embedder


def vector_of(text: str) -> list[float]:
    return [float(len(text)), float(ord(text[0])), 1.0]


class FakeOpenAI:
    """Stands in for openai.OpenAI: records embeddings.create calls and answers from `vector_of`."""

    def __init__(self, reverse=False, drop_last=False, ragged=False, error=None):
        self.inputs: list[list[str]] = []
        self.models: list[str] = []
        self.reverse, self.drop_last, self.ragged, self.error = reverse, drop_last, ragged, error
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, model, input):
        self.models.append(model)
        self.inputs.append(list(input))
        if self.error is not None:
            raise self.error
        data = [SimpleNamespace(index=i, embedding=vector_of(text)) for i, text in enumerate(input)]
        if self.ragged:
            data[-1].embedding = data[-1].embedding + [0.0]
        if self.drop_last:
            data = data[:-1]
        if self.reverse:
            data = data[::-1]
        return SimpleNamespace(data=data)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_batches_and_order():
    client = FakeOpenAI(reverse=True)               # data returned in reverse order
    vectors = LMStudioEmbedder(client, "m", batch_size=2).embed(["a", "b", "c"])
    assert client.inputs == [["a", "b"], ["c"]] and client.models == ["m", "m"]
    assert vectors == [vector_of("a"), vector_of("b"), vector_of("c")]


def test_no_texts_no_call():
    client = FakeOpenAI()
    assert LMStudioEmbedder(client, "m", 32).embed([]) == []
    assert client.inputs == []


def test_fewer_vectors_than_texts():
    with pytest.raises(EmbeddingError, match="2 testi.*1 vettor"):
        LMStudioEmbedder(FakeOpenAI(drop_last=True), "m", 32).embed(["a", "b"])


def test_vectors_of_different_dimensions():
    with pytest.raises(EmbeddingError, match="dimensione"):
        LMStudioEmbedder(FakeOpenAI(ragged=True), "m", 32).embed(["a", "b"])


def test_vectors_of_different_dimensions_across_batches():
    class GrowingOpenAI(FakeOpenAI):
        def create(self, model, input):
            answer = super().create(model, input)
            for item in answer.data:
                item.embedding = item.embedding + [0.0] * len(self.inputs)
            return answer

    with pytest.raises(EmbeddingError, match="dimensione"):
        LMStudioEmbedder(GrowingOpenAI(), "m", 1).embed(["a", "b"])


def test_connection_error_is_italian():
    with pytest.raises(EmbeddingError, match="LM Studio non raggiungibile su http://lm.test/v1"):
        LMStudioEmbedder(FakeOpenAI(error=lm_studio_error()), "m", 32, "http://lm.test/v1").embed(["a"])


def test_timeout_is_italian():
    error = openai.APITimeoutError(request=httpx2.Request("POST", "http://lm.test/v1/embeddings"))
    with pytest.raises(EmbeddingError, match="tempo"):
        LMStudioEmbedder(FakeOpenAI(error=error), "m", 32, "http://lm.test/v1").embed(["a"])


def test_error_answer_is_italian():
    request = httpx2.Request("POST", "http://lm.test/v1/embeddings")
    error = openai.APIStatusError(
        "boom", response=httpx2.Response(400, request=request), body={"error": "not an embedding model"})
    with pytest.raises(EmbeddingError, match="400"):
        LMStudioEmbedder(FakeOpenAI(error=error), "m", 32, "http://lm.test/v1").embed(["a"])


def models_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_model_must_be_listed():
    http = models_client(lambda r: httpx.Response(200, json={"data": [{"id": "altro"}, {"id": "chat"}]}))
    with pytest.raises(EmbeddingError, match="'scelto'.*altro, chat"):
        check_embedding_model("http://lm.test/v1", "scelto", http)


def test_listed_model_passes():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": [{"id": "scelto"}]})

    check_embedding_model("http://lm.test/v1/", "scelto", models_client(handler))
    assert seen == ["http://lm.test/v1/models"]


def test_lm_studio_off_for_the_model_check():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(EmbeddingError, match="LM Studio non raggiungibile su http://lm.test/v1"):
        check_embedding_model("http://lm.test/v1", "scelto", models_client(refuse))


@pytest.mark.parametrize("answer", [httpx.Response(500), httpx.Response(200, text="non json")])
def test_bad_models_answer(answer):
    with pytest.raises(EmbeddingError, match="/models"):
        check_embedding_model("http://lm.test/v1", "scelto", models_client(lambda r: answer))


def test_create_embedder_uses_the_configuration():
    config = load_config({"LMSTUDIO_BASE_URL": "http://lm.test/v1", "EMBEDDING_MODEL": "scelto",
                          "EMBEDDING_BATCH_SIZE": "4"})
    embedder = create_embedder(config)
    assert (embedder.model, embedder.batch_size, embedder.base_url) == ("scelto", 4, "http://lm.test/v1")
    assert str(embedder.client.base_url).rstrip("/") == "http://lm.test/v1"


def test_fake_embedder_is_deterministic_and_close_for_shared_words():
    fake = FakeEmbedder()
    a, b, c = fake.embed(["gnocchi di patate", "patate per gnocchi", "liquore di ciliegie"])
    assert fake.embed(["gnocchi di patate"])[0] == a
    assert dot(a, b) > dot(a, c)
    assert len(a) == FakeEmbedder.DIMENSION and abs(dot(a, a) - 1) < 1e-9
    assert fake.calls == [["gnocchi di patate", "patate per gnocchi", "liquore di ciliegie"],
                          ["gnocchi di patate"]]
