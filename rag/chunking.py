"""Chunking of one recipe (a chunk never spans two recipes).

- paragraph: whole paragraphs packed up to `size`; a paragraph longer than `size` is cut as a window.
- window: windows of `size` characters, at steps of about `size - overlap`.
In both, every chunk after the first starts with the tail of the previous one (at most `overlap`
characters, inside `size`); in `paragraph` the tail shrinks, down to nothing, when it leaves no
room for the next paragraph. Cuts fall on spaces: a word is cut only if longer than a chunk."""

from dataclasses import dataclass

STRATEGIES = ("paragraph", "window")
PARAGRAPH_BREAK = "\n\n"


@dataclass(frozen=True)
class Chunk:
    chunk_index: int  # position in the recipe: 0, 1, ...
    text: str


def split_recipe(text: str, strategy: str, size: int, overlap: int) -> list[Chunk]:
    """Splits the clean text of one recipe; a recipe within `size` is a single chunk."""
    if strategy == "paragraph":
        pieces = _paragraphs(text.strip(), size, overlap)
    elif strategy == "window":
        pieces = _windows(text.strip(), size, overlap)
    else:
        raise ValueError(f"Strategia di chunking sconosciuta: '{strategy}' (ammesse: {', '.join(STRATEGIES)}).")
    return [Chunk(index, piece) for index, piece in enumerate(pieces)]


def _windows(text: str, size: int, overlap: int) -> list[str]:
    """Windows of at most `size` characters ending on a space; each next window starts at a word
    within the last `overlap` characters of the previous one."""
    chunks: list[str] = []
    start, length = 0, len(text)
    while True:
        while start < length and text[start].isspace():
            start += 1
        if start >= length:
            return chunks
        if length - start <= size:
            chunks.append(text[start:].rstrip())
            return chunks
        end = start + size
        cut = end if text[end].isspace() else _last_space(text, start, end)
        chunks.append(text[start:cut].rstrip())
        start = _tail_start(text, max(cut - overlap, start + 1), cut) if overlap else cut


def _last_space(text: str, start: int, end: int) -> int:
    """Index of the last whitespace in text[start+1:end], or `end` (a word longer than a chunk)."""
    for index in range(end - 1, start, -1):
        if text[index].isspace():
            return index
    return end


def _tail_start(text: str, earliest: int, cut: int) -> int:
    """First word start at or after `earliest` and before `cut`; `cut` if there is none."""
    index = earliest
    if not text[index - 1].isspace():
        while index < cut and not text[index].isspace():
            index += 1
    while index < cut and text[index].isspace():
        index += 1
    return index


def _tail(text: str, limit: int) -> str:
    """The last words of `text`, at most `limit` characters ("" if no whole word fits)."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    start = _tail_start(text, len(text) - limit, len(text))
    return text[start:]


def _paragraphs(text: str, size: int, overlap: int) -> list[str]:
    # Units: whole paragraphs, or pieces of a paragraph longer than `size` (the room left for the
    # tail keeps the window overlap inside `size`). `continues`: same paragraph as the unit before.
    units: list[tuple[str, bool]] = []
    for paragraph in (p.strip() for p in text.split(PARAGRAPH_BREAK)):
        if not paragraph:
            continue
        if len(paragraph) <= size:
            units.append((paragraph, False))
        else:
            pieces = _windows(paragraph, size - overlap, 0)
            units.extend((piece, index > 0) for index, piece in enumerate(pieces))

    chunks: list[str] = []
    current = ""
    for unit, continues in units:
        separator = " " if continues else PARAGRAPH_BREAK
        if not current:
            current = unit
        elif len(current) + len(separator) + len(unit) <= size:
            current += separator + unit
        else:
            chunks.append(current)
            tail = _tail(current, min(overlap, size - len(separator) - len(unit)))
            current = tail + separator + unit if tail else unit
    if current:
        chunks.append(current)
    return chunks
