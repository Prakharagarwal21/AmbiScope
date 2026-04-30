from __future__ import annotations


def normalize_arrow(line: str) -> str:
    return line.replace("→", "->")


def strip_inline_comment(line: str) -> str:
    hash_index = line.find("#")
    if hash_index == -1:
        return line
    return line[:hash_index]


def normalize_whitespace(text: str) -> str:
    return " ".join(text.replace("\t", " ").split()).strip()


def unique_name(base: str, used_names: set[str]) -> str:
    if base not in used_names:
        return base
    candidate = base
    while candidate in used_names:
        candidate = candidate + "'"
    return candidate


def sorted_array(values) -> list:
    return sorted(list(values), key=lambda v: (str(v)))

