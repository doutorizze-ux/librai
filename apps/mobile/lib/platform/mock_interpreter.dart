import 'dart:math';
import '../domain/interfaces/sign_interpreter.dart';

class MockSignInterpreter implements SignInterpreter {
  String? _loadedModelPath;
  final double confidenceThreshold = 0.75;

  @override
  Future<void> loadModel(String modelPath) async {
    _loadedModelPath = modelPath;
  }

  @override
  Future<PredictionResult> predict(List<Map<String, double>> landmarks) async {
    if (_loadedModelPath == null) {
      throw StateError("Modelo não carregado. Chame loadModel() primeiro.");
    }

    // Validação estrita de entrada: Landmarks geométricos corrompidos
    if (landmarks.isEmpty || landmarks.length < 2) {
      return PredictionResult(
        label: "DADOS_INSUFICIENTES",
        confidence: 0.0,
        isTestFixture: true,
        modelVersion: "test-v1",
      );
    }

    // Verificar se todos os pontos têm as chaves obrigatórias
    for (final point in landmarks) {
      if (!point.containsKey('x') || !point.containsKey('y') || !point.containsKey('z')) {
        throw ArgumentError("Landmarks devem conter chaves x, y, z");
      }
    }

    // Simulação do cálculo de confiança e previsão
    // Usamos a média do eixo X para simular diferentes sinais
    double sumX = 0;
    for (final p in landmarks) {
      sumX += p['x'] ?? 0.5;
    }
    final avgX = sumX / landmarks.length;

    String predictedLabel;
    double confidence;

    if (avgX > 0.45 && avgX < 0.55) {
      predictedLabel = "AJUDA";
      confidence = 0.88;
    } else if (avgX >= 0.55 && avgX < 0.65) {
      predictedLabel = "SAÚDE";
      confidence = 0.92;
    } else if (avgX >= 0.35 && avgX <= 0.45) {
      predictedLabel = "BOM_DIA";
      confidence = 0.81;
    } else {
      // Gestos aleatórios fora dos padrões conhecidos
      predictedLabel = "GESTO_DESCONHECIDO";
      confidence = 0.45; // Baixa confiança
    }

    // SISTEMA DE REJEIÇÃO: Limiar estatístico contra alucinações de sinais
    if (confidence < confidenceThreshold) {
      return PredictionResult(
        label: "SINAL_DESCONHECIDO",
        confidence: confidence,
        isTestFixture: true,
        modelVersion: "test-v1",
      );
    }

    return PredictionResult(
      label: predictedLabel,
      confidence: confidence,
      isTestFixture: true,
      modelVersion: "test-v1",
    );
  }
}
