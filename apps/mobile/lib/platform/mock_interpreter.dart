import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../domain/interfaces/sign_interpreter.dart';
import 'app_config.dart';

class MockSignInterpreter implements SignInterpreter {
  static const int _minimumHolisticFrames = 24;
  static const int _maximumHolisticFrames = 40;
  static const int _holisticPredictionStride = 6;

  String? _loadedModelPath;
  final double confidenceThreshold = 0.75;
  final List<List<Map<String, double>>> _sequenceFrames = [];
  final List<Map<String, dynamic>> _structuredSequenceFrames = [];
  final List<Map<String, dynamic>> _holisticSequenceFrames = [];
  int _structuredFramesSincePrediction = 0;
  int _holisticFramesSincePrediction = 0;

  final Dio _dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiUrl,
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 5),
    sendTimeout: const Duration(seconds: 5),
    persistentConnection: true,
    headers: const {'Content-Type': 'application/json'},
  ));

  @override
  Future<void> loadModel(String modelPath) async {
    _loadedModelPath = modelPath;
  }

  void resetSequence() {
    _sequenceFrames.clear();
    _structuredSequenceFrames.clear();
    _holisticSequenceFrames.clear();
    _structuredFramesSincePrediction = 0;
    _holisticFramesSincePrediction = 0;
  }

  void addHandFrame(Map<String, dynamic> frame) {
    final hands = frame['hands'];
    if (hands is! List || hands.isEmpty) return;
    _structuredSequenceFrames.add(Map<String, dynamic>.from(frame));
    _structuredFramesSincePrediction++;
    if (_structuredSequenceFrames.length > 64) {
      _structuredSequenceFrames.removeAt(0);
    }
  }

  // Menos de 24 quadros representa apenas o início de muitos sinais e pode
  // coincidir com outro gesto. Depois disso, analisamos a cada seis quadros.
  bool get hasEnoughHandFrames =>
      _structuredSequenceFrames.length >= 24 &&
      _structuredFramesSincePrediction >= 6;

  void addHolisticFrame(Map<String, dynamic> frame) {
    final hands = frame['hands'];
    final pose = frame['pose'];
    final expression = frame['expression'];
    if (hands is! List || hands.isEmpty || pose is! Map || expression is! Map) {
      return;
    }
    _holisticSequenceFrames.add(Map<String, dynamic>.from(frame));
    _holisticFramesSincePrediction++;
    if (_holisticSequenceFrames.length > _maximumHolisticFrames) {
      _holisticSequenceFrames.removeAt(0);
    }
  }

  bool get hasEnoughHolisticFrames =>
      _holisticSequenceFrames.length >= _minimumHolisticFrames &&
      _holisticFramesSincePrediction >= _holisticPredictionStride;

  @visibleForTesting
  int get bufferedHolisticFrameCount => _holisticSequenceFrames.length;

  @visibleForTesting
  int get holisticFramesSincePrediction => _holisticFramesSincePrediction;

  Future<PredictionResult> predictBufferedHolisticSequence() async {
    if (_loadedModelPath == null) {
      throw StateError("Modelo não carregado. Chame loadModel() primeiro.");
    }
    if (!hasEnoughHolisticFrames) {
      return PredictionResult(
        label: "DADOS_INSUFICIENTES",
        confidence: 0,
        isTestFixture: false,
        modelVersion: "holistic_sequence_v4",
      );
    }
    final snapshot = _holisticSequenceFrames
        .map((frame) => Map<String, dynamic>.from(frame))
        .toList(growable: false);
    _holisticFramesSincePrediction = 0;
    try {
      final response = await _dio.post(
        '/v1/translation/predict-sequence-v4',
        data: {'format_version': 4, 'frames': snapshot},
      );
      return PredictionResult(
        label: response.data['label'] as String,
        confidence: (response.data['confidence'] as num).toDouble(),
        isTestFixture: false,
        modelVersion:
            response.data['model'] as String? ?? "holistic_sequence_v4",
      );
    } catch (e) {
      debugPrint("[Remote Interpreter v4] Falha: $e");
      return PredictionResult(
        label: "SINAL_DESCONHECIDO",
        confidence: 0,
        isTestFixture: false,
        modelVersion: "holistic_sequence_v4",
      );
    }
  }

  Future<PredictionResult> predictBufferedSequence() async {
    if (_loadedModelPath == null) {
      throw StateError("Modelo não carregado. Chame loadModel() primeiro.");
    }
    if (!hasEnoughHandFrames) {
      return PredictionResult(
        label: "DADOS_INSUFICIENTES",
        confidence: 0,
        isTestFixture: false,
        modelVersion: "two_hand_sequence_v2",
      );
    }
    final snapshot = _structuredSequenceFrames
        .map((frame) => Map<String, dynamic>.from(frame))
        .toList(growable: false);
    _structuredFramesSincePrediction = 0;
    try {
      final response = await _dio.post(
        '/v1/translation/predict-sequence-v2',
        data: {'format_version': 2, 'frames': snapshot},
      );
      return PredictionResult(
        label: response.data['label'] as String,
        confidence: (response.data['confidence'] as num).toDouble(),
        isTestFixture: false,
        modelVersion:
            response.data['model'] as String? ?? "two_hand_sequence_v2",
      );
    } catch (e) {
      debugPrint("[Remote Interpreter v2] Falha: $e");
      return PredictionResult(
        label: "SINAL_DESCONHECIDO",
        confidence: 0,
        isTestFixture: false,
        modelVersion: "two_hand_sequence_v2",
      );
    }
  }

  Future<PredictionResult> predictHandFrame(Map<String, dynamic> frame) {
    addHandFrame(frame);
    return predictBufferedSequence();
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
      if (!point.containsKey('x') ||
          !point.containsKey('y') ||
          !point.containsKey('z')) {
        throw ArgumentError("Landmarks devem conter chaves x, y, z");
      }
    }

    final bool isTest =
        _loadedModelPath != null && _loadedModelPath!.contains("test_");

    if (!isTest) {
      _sequenceFrames.add(
        landmarks
            .map((point) => Map<String, double>.from(point))
            .toList(growable: false),
      );
      if (_sequenceFrames.length > 48) {
        _sequenceFrames.removeAt(0);
      }
      if (_sequenceFrames.length < 12) {
        return PredictionResult(
          label: "DADOS_INSUFICIENTES",
          confidence: 0,
          isTestFixture: false,
          modelVersion: "hand_sequence_v1",
        );
      }

      final lastIndex = _sequenceFrames.length - 1;
      final sampledFrames = List<List<Map<String, double>>>.generate(
        20,
        (index) => _sequenceFrames[(index * lastIndex / 19).round()],
        growable: false,
      );
      try {
        // O servidor compara a trajetória completa, não poses isoladas.
        final response = await _dio.post(
          '/v1/translation/predict-sequence',
          data: {'frames': sampledFrames},
        );

        if (response.statusCode == 200) {
          final label = response.data['label'] as String;
          final confidence = (response.data['confidence'] as num).toDouble();

          return PredictionResult(
            label: label,
            confidence: confidence,
            isTestFixture: false,
            modelVersion:
                response.data['model'] as String? ?? "hand_sequence_v1",
          );
        }
      } catch (e) {
        debugPrint("[Remote Interpreter] Falha na predição temporal: $e");
      }

      // Nunca inventar uma tradução de demonstração em uma sessão real.
      return PredictionResult(
        label: "SINAL_DESCONHECIDO",
        confidence: 0,
        isTestFixture: false,
        modelVersion: "hand_sequence_v1",
      );
    }

    // Simulação do cálculo de confiança e previsão (Fallback Local)
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
      predictedLabel = "GESTO_DESCONHECIDO";
      confidence = 0.45;
    }

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
