class ReferenceSign {
  const ReferenceSign({
    required this.id,
    required this.label,
    required this.platforms,
    required this.isCompound,
  });

  final String id;
  final String label;
  final List<String> platforms;
  final bool isCompound;
}
