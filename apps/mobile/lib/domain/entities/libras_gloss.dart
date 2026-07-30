class LibrasGloss {
  LibrasGloss(String value) : value = normalize(value);

  final String value;

  String get displayLabel => value.replaceAll('_', ' ');

  static String normalize(String value) {
    return value.trim().replaceAll(RegExp(r'\s+'), ' ').toUpperCase();
  }

  static LibrasGloss fromLabels(Iterable<String> labels) {
    return LibrasGloss(labels.map(normalize).join(' '));
  }
}
