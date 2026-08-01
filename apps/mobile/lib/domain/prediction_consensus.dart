class PredictionConsensus {
  PredictionConsensus({
    this.requiredConsecutiveMatches = 2,
    this.minimumConfidence = 0.75,
  }) : assert(requiredConsecutiveMatches > 0);

  final int requiredConsecutiveMatches;
  final double minimumConfidence;

  String? _candidate;
  int _consecutiveMatches = 0;

  String? accept({
    required String label,
    required double confidence,
  }) {
    final normalized = label.trim().toUpperCase();
    if (_isRejected(normalized, confidence)) {
      reset();
      return null;
    }

    if (_candidate == normalized) {
      _consecutiveMatches++;
    } else {
      _candidate = normalized;
      _consecutiveMatches = 1;
    }

    if (_consecutiveMatches < requiredConsecutiveMatches) return null;
    final confirmed = _candidate;
    reset();
    return confirmed;
  }

  void reset() {
    _candidate = null;
    _consecutiveMatches = 0;
  }

  bool _isRejected(String label, double confidence) {
    return confidence < minimumConfidence ||
        label.isEmpty ||
        label == 'SINAL_DESCONHECIDO' ||
        label == 'SINAL_AMBIGUO' ||
        label == 'DADOS_INSUFICIENTES';
  }
}
