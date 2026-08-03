class LexicalSignLabel {
  static final RegExp _allowed = RegExp(
    r"^[A-Za-zÀ-ÖØ-ö0-9]+"
    r"(?:[ -'][A-Za-zÀ-ÖØ-ö0-9]+)*"
    r"[?!]?$",
  );

  /// Normalizes the Portuguese display label but keeps it as one Libras class.
  /// Whitespace is never interpreted as a boundary between visual signs.
  static String normalize(String rawLabel) =>
      rawLabel.trim().replaceAll(RegExp(r'\s+'), ' ').toUpperCase();

  static bool isValid(String rawLabel) {
    final normalized = normalize(rawLabel);
    return normalized.isNotEmpty &&
        normalized.length <= 64 &&
        _allowed.hasMatch(normalized);
  }
}
