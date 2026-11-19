"""Embeddings from LM Studio (/v1/embeddings, OpenAI-compatible) and the check of the model.

The same method embeds chunks and questions: no prefix or other transformation between the two."""

from collections.abc import Sequence
from typing import Protocol

import httpx
import openai

from rag.config import RagConfig

EMBEDDING_TIMEOUT = 60.0  # one batch; the first call may also load the model
CHECK_TIMEOUT = 5.0  # GET /models does not load the model


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class EmbeddingError(Exception):
    """LM Studio unreachable, model not available, or an answer that cannot be used."""


class LMStudioEmbedder:
    """Embeds texts in batches of `batch_size`, keeping their order. `client` offers
    `client.embeddings.create(model=..., input=[...])` (openai.OpenAI in use)."""

    def __init__(self, client, model: str, batch_size: int, base_url: str = "") -> None:
        self.client = client
        self.model = model
        self.batch_size = batch_size
        self.base_url = base_url or str(getattr(client, "base_url", "")).rstrip("/")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start:start + self.batch_size])
            vectors.extend(self._embed_batch(batch))
        if len({len(vector) for vector in vectors}) > 1:
            raise EmbeddingError(
                f"LM Studio ha restituito vettori di dimensione diversa ({self._sizes(vectors)}) "
                f"con il modello '{self.model}'."
            )
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            answer = self.client.embeddings.create(model=self.model, input=batch)
        except openai.APITimeoutError:
            raise EmbeddingError(
                f"LM Studio su {self.base_url} non ha risposto in tempo agli embedding "
                f"({EMBEDDING_TIMEOUT:.0f} s)."
            ) from None
        except openai.APIConnectionError:
            raise EmbeddingError(f"LM Studio non raggiungibile su {self.base_url}.") from None
        except openai.APIStatusError as error:
            raise EmbeddingError(
                f"LM Studio su {self.base_url} ha risposto {error.status_code} alla richiesta di "
                f"embedding con il modello '{self.model}': è un modello di embedding?"
            ) from None
        data = sorted(answer.data, key=lambda item: item.index)
        if len(data) != len(batch) or [item.index for item in data] != list(range(len(batch))):
            raise EmbeddingError(
                f"Inviati {len(batch)} testi, LM Studio ha restituito {len(data)} vettori: "
                "nessun punto scritto, per non associare un vettore al testo sbagliato."
            )
        return [list(item.embedding) for item in data]

    @staticmethod
    def _sizes(vectors: list[list[float]]) -> str:
        return ", ".join(str(size) for size in sorted({len(vector) for vector in vectors}))


def create_embedder(config: RagConfig) -> LMStudioEmbedder:
    client = openai.OpenAI(
        base_url=config.base_url, api_key="lm-studio", timeout=EMBEDDING_TIMEOUT, max_retries=0,
    )
    return LMStudioEmbedder(client, config.embedding_model, config.batch_size, config.base_url)


def check_embedding_model(base_url: str, model: str, http: httpx.Client | None = None) -> None:
    """EmbeddingError unless LM Studio answers GET <base_url>/models and lists `model`.
    `http` replaces the HTTP client in the tests."""
    url = f"{base_url.rstrip('/')}/models"
    try:
        if http is None:
            response = httpx.get(url, timeout=CHECK_TIMEOUT)
        else:
            response = http.get(url, timeout=CHECK_TIMEOUT)
    except httpx.HTTPError:
        raise EmbeddingError(f"LM Studio non raggiungibile su {base_url.rstrip('/')}.") from None
    if response.status_code != 200:
        raise EmbeddingError(f"LM Studio ha risposto {response.status_code} a GET {url}.")
    try:
        ids = [entry["id"] for entry in response.json()["data"]]
    except (ValueError, KeyError, TypeError):
        raise EmbeddingError(f"Risposta non valida di LM Studio a GET {url}.") from None
    if model not in ids:
        available = ", ".join(ids) if ids else "nessuno"
        raise EmbeddingError(
            f"Il modello di embedding '{model}' (EMBEDDING_MODEL) non è tra quelli di LM Studio: "
            f"{available}. Caricarlo in LM Studio o correggere EMBEDDING_MODEL."
        )
