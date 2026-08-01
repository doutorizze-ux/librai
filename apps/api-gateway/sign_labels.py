import re


VISUAL_LABEL_ALIASES = {
    "BOA": "BOM",
}

_ISOLATED_SIGN_PATTERN = re.compile(
    r"^[A-ZÀ-ÖØ-Ý0-9]+(?:[-'][A-ZÀ-ÖØ-Ý0-9]+)*$"
)


def canonical_visual_label(raw_label: str) -> str:
    """Retorna a glosa visual única para sinais com variação só em português."""
    normalized = raw_label.upper().strip()
    return VISUAL_LABEL_ALIASES.get(normalized, normalized)


def is_isolated_sign_label(raw_label: str) -> bool:
    normalized = canonical_visual_label(raw_label)
    return bool(normalized and _ISOLATED_SIGN_PATTERN.fullmatch(normalized))
