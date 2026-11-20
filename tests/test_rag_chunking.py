"""Chunking of a recipe: paragraph and window strategies, overlap, cuts on spaces."""

import pytest

from rag.chunking import STRATEGIES, Chunk, indexed_text, split_recipe


def words(prefix: str, start: int, count: int) -> str:
    return " ".join(f"{prefix}{i:03d}" for i in range(start, start + count))


SHORT = words("breve", 0, 33)                                           # 296 characters
LONG = "\n\n".join(words("parola", 40 * p, 40) for p in range(8))
HUGE_PARAGRAPH = words("lungo", 0, 333)                                 # 2996 characters


def test_texts_have_the_intended_shape():
    assert len(SHORT) < 1200 and len(HUGE_PARAGRAPH) > 2900 and "\n" not in HUGE_PARAGRAPH
    paragraphs = LONG.split("\n\n")
    assert len(paragraphs) == 8 and all(len(p) == 399 for p in paragraphs)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_short_recipe_is_one_chunk(strategy):
    assert split_recipe(SHORT, strategy, 1200, 200) == [Chunk(0, SHORT)]


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("text", [LONG, HUGE_PARAGRAPH], ids=["long", "huge-paragraph"])
def test_long_recipe(strategy, text):
    chunks = split_recipe(text, strategy, 1200, 200)
    assert len(chunks) > 1 and [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(len(c.text) <= 1200 for c in chunks)
    all_words = set(text.split())
    assert all(set(c.text.split()) <= all_words for c in chunks)              # no word cut
    assert set().union(*(c.text.split() for c in chunks)) == all_words        # no text lost


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("text", [LONG, HUGE_PARAGRAPH], ids=["long", "huge-paragraph"])
def test_chunks_overlap(strategy, text):
    chunks = split_recipe(text, strategy, 1200, 200)
    for previous, current in zip(chunks, chunks[1:]):
        head = current.text.split()[0]
        assert head in previous.text.split()
        assert previous.text.split().index(head) >= len(previous.text.split()) - 25  # a tail


def test_paragraph_chunks_keep_whole_paragraphs():
    for chunk in split_recipe(LONG, "paragraph", 1200, 200):
        for paragraph in chunk.text.split("\n\n")[1:]:   # the first piece can be the repeated tail
            assert paragraph in LONG.split("\n\n")


def test_paragraph_overlap_shrinks_to_fit_the_next_paragraph():
    first = " ".join(f"uno{i:03d}" for i in range(100))      # 699 characters
    second = " ".join(f"due{i:03d}" for i in range(143))     # 1000 characters: no room for the tail
    chunks = split_recipe(first + "\n\n" + second, "paragraph", 1000, 200)
    assert [c.text for c in chunks] == [first, second]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_zero_overlap_repeats_nothing(strategy):
    chunks = split_recipe(LONG, strategy, 1200, 0)
    assert sum(len(c.text.split()) for c in chunks) == len(LONG.split())


def test_window_steps_by_size_minus_overlap():
    chunks = split_recipe(HUGE_PARAGRAPH, "window", 1000, 200)
    assert len(chunks) == 4                     # 2996 characters, steps of about 800
    assert all(len(c.text) > 950 for c in chunks[:-1])


def test_word_longer_than_the_chunk_is_the_only_cut():
    long_word = "x" * 250
    chunks = split_recipe(f"inizio {long_word} fine", "window", 100, 20)
    assert "".join(c.text.replace(" ", "") for c in chunks).count("x") >= 250
    assert all(len(c.text) <= 100 for c in chunks)


def test_unknown_strategy():
    with pytest.raises(ValueError, match="sentence"):
        split_recipe(SHORT, "sentence", 1200, 200)


def test_indexed_text_with_title_and_chapter():
    assert indexed_text("Pollo alla cacciatora", "Fritti", "Prendete un pollo.", "title_chapter") == (
        "Pollo alla cacciatora (capitolo Fritti)\n\nPrendete un pollo.")


def test_indexed_text_without_header():
    assert indexed_text("Pollo alla cacciatora", "Fritti", "Prendete un pollo.", "none") == "Prendete un pollo."


def test_indexed_text_unknown_header():
    with pytest.raises(ValueError, match="altro"):
        indexed_text("Pollo alla cacciatora", "Fritti", "Prendete un pollo.", "altro")
