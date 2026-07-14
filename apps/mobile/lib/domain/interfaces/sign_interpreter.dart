class PredictionResult {
  final String label;
  final double confidence;
  final bool isTestFixture;
  final String? modelVersion;

  PredictionResult({
    required this.label,
    required this.confidence,
    required this.isTestFixture,
    this.modelVersion,
  });

  @override
  String toString() {
    return 'PredictionResult(label: $label, confidence: $confidence, isTestFixture: $isTestFixture)';
  }
}

abstract class SignInterpreter {
  Future<void> loadModel(String modelPath);
  Future<PredictionResult> predict(List<Map<String, double>> landmarks);
}
