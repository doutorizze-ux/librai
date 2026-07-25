class ReferenceSequenceSign {
  const ReferenceSequenceSign({
    required this.label,
    required this.motionReady,
  });

  final String label;
  final bool motionReady;
}

class ReferenceSequence {
  const ReferenceSequence({
    required this.sourceText,
    required this.signs,
    required this.unresolved,
  });

  final String sourceText;
  final List<ReferenceSequenceSign> signs;
  final List<String> unresolved;
}
