class RecognitionPolicy {
  const RecognitionPolicy._();

  /// Letras isoladas não podem ser aceitas pelo classificador de poses.
  ///
  /// Uma configuração do alfabeto manual também pode ser o início ou parte de
  /// um sinal dinâmico (por exemplo, D e DIA). A soletração só deve voltar a
  /// ser habilitada quando existir um modo temporal dedicado.
  static bool isUnsupportedStaticAlphabetPrediction(String rawLabel) {
    final label = rawLabel.trim().toUpperCase();
    return label.length == 1 && RegExp(r'^[A-Z]$').hasMatch(label);
  }
}
