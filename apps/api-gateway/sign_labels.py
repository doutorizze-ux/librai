VISUAL_LABEL_ALIASES = {
    "BOA": "BOM",
}


def canonical_visual_label(raw_label: str) -> str:
    """Retorna a glosa visual única para sinais com variação só em português."""
    normalized = raw_label.upper().strip()
    return VISUAL_LABEL_ALIASES.get(normalized, normalized)
