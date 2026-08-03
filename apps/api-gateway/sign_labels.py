import re


VISUAL_LABEL_ALIASES = {
    "BOA": "BOM",
}

_ISOLATED_SIGN_PATTERN = re.compile(
    r"^[A-ZÀ-ÖØ-Ý0-9]+(?:[-'][A-ZÀ-ÖØ-Ý0-9]+)*$"
)

# A lexical unit is one Libras sign, not necessarily one Portuguese word.
# Examples such as "TUDO BEM?" must remain a single class and must never be
# split merely because the display label contains whitespace.
_LEXICAL_UNIT_PATTERN = re.compile(
    r"^[A-ZÀ-ÖØ-Ý0-9]+"
    r"(?:[ -'][A-ZÀ-ÖØ-Ý0-9]+)*"
    r"[?!]?$"
)


def canonical_visual_label(raw_label: str) -> str:
    """Retorna a glosa visual única para sinais com variação só em português."""
    normalized = raw_label.upper().strip()
    return VISUAL_LABEL_ALIASES.get(normalized, normalized)


def is_isolated_sign_label(raw_label: str) -> bool:
    normalized = canonical_visual_label(raw_label)
    return bool(normalized and _ISOLATED_SIGN_PATTERN.fullmatch(normalized))


def canonical_lexical_unit_label(raw_label: str) -> str:
    """Normalize one semantic Libras unit without tokenizing its PT-BR label."""
    normalized = " ".join(raw_label.upper().strip().split())
    return VISUAL_LABEL_ALIASES.get(normalized, normalized)


def is_lexical_unit_label(raw_label: str) -> bool:
    normalized = canonical_lexical_unit_label(raw_label)
    return bool(normalized and _LEXICAL_UNIT_PATTERN.fullmatch(normalized))
