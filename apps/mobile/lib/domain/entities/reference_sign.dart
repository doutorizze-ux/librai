class ReferenceSign {
  const ReferenceSign({
    required this.id,
    required this.label,
    required this.platforms,
    required this.isCompound,
    required this.motionReady,
  });

  final String id;
  final String label;
  final List<String> platforms;
  final bool isCompound;
  final bool motionReady;
}
