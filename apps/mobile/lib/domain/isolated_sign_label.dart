class IsolatedSignLabel {
  static final RegExp _allowed = RegExp(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*$",
  );

  static String normalize(String rawLabel) => rawLabel.trim().toUpperCase();

  static bool isValid(String rawLabel) {
    final normalized = normalize(rawLabel);
    return normalized.isNotEmpty &&
        normalized.length <= 40 &&
        _allowed.hasMatch(normalized);
  }
}
