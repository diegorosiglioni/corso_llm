"""Rule `has_doses`: does a chunk contain a list of ingredients? (spec 2026-11-20, §3)

The corpus cleaning joins prose into one-line paragraphs; only dose lists, some verses and the
`[Illustrazione: …]` captions keep several lines. So a chunk has doses when it contains at least one
paragraph (block separated by an empty line) of two or more non-empty lines, not starting with
`[Illustrazione`, with at least one line holding a quantity: grammi, gr., decilitri, litro/litri,
chilogrammi, N. followed by a number, quanto basta, cucchiaio/cucchiai/cucchiaiata/cucchiaiate,
bicchiere/bicchieri, etto/etti. Lists without units (a few recipes, e.g. 99 and 308) stay false.

Pure function: used by the ingestion and by `python -m rag.update_payload` on the stored text."""

import re

QUANTITY = re.compile(
    r"\b(?:grammi|gr\.|decilitri|litr[oi]|chilogrammi|N\.\s*\d+|quanto\s+basta"
    r"|cucchiai(?:o|ata|ate)?|bicchier[ei]|ett[oi])(?!\w)",
    re.IGNORECASE,
)


def has_doses(text: str) -> bool:
    """True if `text` contains a multi-line paragraph, not a caption, with a quantity."""
    for paragraph in text.split("\n\n"):
        lines = [line for line in paragraph.split("\n") if line.strip()]
        if len(lines) < 2 or lines[0].lstrip().startswith("[Illustrazione"):
            continue
        if any(QUANTITY.search(line) for line in lines):
            return True
    return False
