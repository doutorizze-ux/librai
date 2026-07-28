class AssistedPredictionCandidate {
  const AssistedPredictionCandidate({
    required this.label,
    required this.confidence,
  });

  final String label;
  final double confidence;
}

class AssistedPrediction {
  const AssistedPrediction({required this.model, required this.candidates});

  final String model;
  final List<AssistedPredictionCandidate> candidates;
}
