from __future__ import annotations


SMART_CHAR_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201C": '"',
    "\u201D": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u00A0": " ",
}


def normalize_text(text: str) -> tuple[str, list[int]]:
    """Normalize text while preserving a map from normalized chars to raw indices."""
    normalized_chars: list[str] = []
    offset_map: list[int] = []
    pending_space_index: int | None = None

    for raw_index, original_char in enumerate(text):
        char = SMART_CHAR_MAP.get(original_char, original_char)
        is_space = char.isspace()

        if is_space:
            if normalized_chars:
                pending_space_index = raw_index if pending_space_index is None else pending_space_index
            continue

        if pending_space_index is not None:
            normalized_chars.append(" ")
            offset_map.append(pending_space_index)
            pending_space_index = None

        for lowered_char in char.lower():
            normalized_chars.append(lowered_char)
            offset_map.append(raw_index)

    return "".join(normalized_chars), offset_map
