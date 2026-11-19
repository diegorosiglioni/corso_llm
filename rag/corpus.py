"""Artusi's book (Project Gutenberg 59047): the 790 recipes with title, chapter and clean text.

Only the recipes are kept: header and license (outside the Gutenberg markers), preface, chapter
introductions and the appendix are excluded. Chapters come from a fixed list, not from a rule on
upper case: the book has upper-case lines that are not chapters."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chapter:
    heading: str  # upper-case line as it is in the file
    name: str  # name saved with the recipe and used by the chapter filter


CHAPTERS: tuple[Chapter, ...] = tuple(Chapter(name.upper(), name) for name in (
    "Brodi, gelatina e sughi", "Minestre in brodo", "Minestre asciutte e di magro", "Principii",
    "Salse", "Uova", "Paste e pastelle", "Ripieni", "Fritti", "Lesso", "Tramessi", "Umidi",
    "Rifreddi", "Erbaggi e legumi", "Piatti di pesce", "Arrosti", "Pasticceria",
    "Torte e dolci al cucchiaio", "Siroppi", "Conserve", "Liquori", "Gelati", "Cose diverse",
))
EXPECTED_RECIPES = 790
# Headings that group chapters (MINESTRE covers the two chapters of soups): they end the current
# recipe and their introduction, like a chapter's, belongs to no recipe.
GROUP_HEADINGS = ("MINESTRE",)
END_OF_RECIPES = "APPENDICE"
START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK"

TITLE = re.compile(r"^(\d+)\. (.+)$")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
SPACES = re.compile(r" {2,}")


@dataclass(frozen=True)
class Recipe:
    number: int
    title: str
    chapter: str
    text: str


class CorpusError(Exception):
    """The book is unreadable or does not have the expected structure."""


def load_corpus(
    path: str | Path,
    chapters: Sequence[Chapter] = CHAPTERS,
    expected: int = EXPECTED_RECIPES,
) -> list[Recipe]:
    """Reads the book in UTF-8 (with or without BOM) and returns its recipes."""
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise CorpusError(f"Impossibile leggere il libro '{path}': {error.strerror or error}.") from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CorpusError(f"Il libro '{path}' non è un testo UTF-8.") from None
    return parse_corpus(text, chapters, expected)


def parse_corpus(
    raw: str,
    chapters: Sequence[Chapter] = CHAPTERS,
    expected: int = EXPECTED_RECIPES,
) -> list[Recipe]:
    """Splits the book into recipes and checks numbering and chapters (first problem found)."""
    # Only real line ends: splitlines() would also split on control characters such as \x0c.
    raw_lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip() for line in _between_markers(raw_lines)]

    def is_heading(index: int, heading: str) -> bool:
        return (lines[index] == heading
                and (index == 0 or not lines[index - 1])
                and (index + 1 == len(lines) or not lines[index + 1]))

    first = next((i for i in range(len(lines)) if is_heading(i, chapters[0].heading)), None)
    if first is None:
        raise CorpusError(f"Capitolo '{chapters[0].heading}' non trovato: il libro non è quello atteso.")
    end = next((i for i in range(first, len(lines)) if is_heading(i, END_OF_RECIPES)), None)
    if end is None:
        raise CorpusError(f"Riga '{END_OF_RECIPES}' non trovata dopo le ricette.")

    recipes: list[Recipe] = []
    found_chapters = 0
    chapter = ""
    title = ""
    body: list[str] | None = None  # None: outside a recipe (introductions are discarded)

    def close() -> None:
        if body is not None:
            recipes.append(Recipe(len(recipes) + 1, title, chapter, clean_text(body)))

    for index in range(first, end):
        line = lines[index]
        if found_chapters < len(chapters) and is_heading(index, chapters[found_chapters].heading):
            close()
            chapter, body = chapters[found_chapters].name, None
            found_chapters += 1
            continue
        if any(is_heading(index, heading) for heading in GROUP_HEADINGS):
            close()
            body = None
            continue
        match = TITLE.match(line)
        if (match and int(match.group(1)) == len(recipes) + (body is not None) + 1
                and not lines[index - 1]):
            close()
            title, body = _clean_line(match.group(2)), []
            continue
        if body is not None:
            body.append(line)
    close()

    _check(recipes, chapters, found_chapters, expected)
    return recipes


def _between_markers(lines: list[str]) -> list[str]:
    start = next((i + 1 for i, line in enumerate(lines) if line.startswith(START_MARKER)), 0)
    stop = next((i for i, line in enumerate(lines) if line.startswith(END_MARKER)), len(lines))
    return lines[start:stop]


def _check(recipes: list[Recipe], chapters: Sequence[Chapter], found: int, expected: int) -> None:
    if found < len(chapters):
        raise CorpusError(f"Capitolo '{chapters[found].heading}' non trovato (atteso dopo "
                          f"'{chapters[found - 1].heading}').")
    if len(recipes) != expected:
        raise CorpusError(f"Trovate {len(recipes)} ricette su {expected}: "
                          f"manca la ricetta numero {len(recipes) + 1}.")
    with_recipes = {recipe.chapter for recipe in recipes}
    for item in chapters:
        if item.name not in with_recipes:
            raise CorpusError(f"Il capitolo '{item.name}' non ha ricette.")
    for recipe in recipes:
        if not recipe.title or not recipe.text:
            raise CorpusError(f"La ricetta {recipe.number} ha il titolo o il testo vuoto.")


def _clean_line(line: str) -> str:
    return SPACES.sub(" ", CONTROL.sub("", line).replace("_", "")).strip()


def clean_text(lines: Sequence[str]) -> str:
    """Joins wrapped lines into paragraphs (separated by a blank line); indented lines (doses,
    verses) stay separate lines without the indent; italics underscores and control characters
    removed, multiple spaces collapsed."""
    paragraphs: list[list[str]] = [[]]
    joinable = False  # whether the last output line is a wrapped (non-indented) line
    for raw in lines:
        if not raw.strip():
            if paragraphs[-1]:
                paragraphs.append([])
            joinable = False
            continue
        line = _clean_line(raw)
        if not line:
            continue
        indented = raw[:1].isspace()
        if joinable and not indented:
            paragraphs[-1][-1] += " " + line
        else:
            paragraphs[-1].append(line)
        joinable = not indented
    return "\n\n".join("\n".join(paragraph) for paragraph in paragraphs if paragraph)
