import 'dart:convert';
import 'dart:math' as math;

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../domain/interfaces/sign_interpreter.dart';
import '../platform/app_config.dart';

class TrainingFeature {
  const TrainingFeature({required this.label, required this.angles});

  final String label;
  final List<double> angles;

  factory TrainingFeature.fromJson(Map<String, dynamic> json) {
    return TrainingFeature(
      label: json['label'] as String,
      angles: (json['angles'] as List<dynamic>)
          .map((value) => (value as num).toDouble())
          .toList(growable: false),
    );
  }
}

class NativeTrainingModel {
  const NativeTrainingModel({
    required this.version,
    required this.threshold,
    required this.features,
  });

  final String version;
  final double threshold;
  final List<TrainingFeature> features;

  bool get isReady => features.isNotEmpty;

  factory NativeTrainingModel.fromJson(Map<String, dynamic> json) {
    if (json['feature_schema'] != 'hand_angles_v1') {
      throw const FormatException('Esquema de treinamento incompatível.');
    }

    return NativeTrainingModel(
      version: json['version'] as String,
      threshold: (json['threshold'] as num).toDouble(),
      features: (json['features'] as List<dynamic>)
          .map(
            (feature) =>
                TrainingFeature.fromJson(feature as Map<String, dynamic>),
          )
          .toList(growable: false),
    );
  }
}

class NativeModelRepository {
  NativeModelRepository()
      : _dio = Dio(
          BaseOptions(
            baseUrl: AppConfig.apiUrl,
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 20),
            persistentConnection: true,
          ),
        );

  static const _cacheKey = 'librai_native_training_model_v1';
  final Dio _dio;
  final SharedPreferencesAsync _preferences = SharedPreferencesAsync();

  Future<NativeTrainingModel> synchronize() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/v1/training/model/current',
      );
      final payload = response.data;
      if (payload == null) {
        throw const FormatException('Modelo vazio recebido do servidor.');
      }
      final model = NativeTrainingModel.fromJson(payload);
      await _preferences.setString(_cacheKey, jsonEncode(payload));
      return model;
    } catch (_) {
      final cached = await _preferences.getString(_cacheKey);
      if (cached == null) rethrow;
      return NativeTrainingModel.fromJson(
        jsonDecode(cached) as Map<String, dynamic>,
      );
    }
  }
}

class LocalKnnInterpreter {
  NativeTrainingModel? _model;

  void load(NativeTrainingModel model) {
    _model = model;
  }

  PredictionResult predict(List<Map<String, double>> landmarks) {
    final model = _model;
    if (model == null || !model.isReady || landmarks.length != 21) {
      return PredictionResult(
        label: 'DADOS_INSUFICIENTES',
        confidence: 0,
        isTestFixture: false,
        modelVersion: model?.version,
      );
    }

    final inputAngles = _extractAngles(landmarks);
    var bestLabel = 'SINAL_DESCONHECIDO';
    var minimumDistance = double.infinity;

    for (final feature in model.features) {
      if (feature.angles.length != inputAngles.length) continue;
      var squaredDistance = 0.0;
      for (var index = 0; index < inputAngles.length; index++) {
        final difference = inputAngles[index] - feature.angles[index];
        squaredDistance += difference * difference;
      }
      final distance = math.sqrt(squaredDistance);
      if (distance < minimumDistance) {
        minimumDistance = distance;
        bestLabel = feature.label;
      }
    }

    if (minimumDistance >= model.threshold) {
      return PredictionResult(
        label: 'SINAL_DESCONHECIDO',
        confidence: 0,
        isTestFixture: false,
        modelVersion: model.version,
      );
    }

    final confidence = math.max(
      0.5,
      1 - (minimumDistance / model.threshold) * 0.5,
    ).toDouble();
    return PredictionResult(
      label: bestLabel,
      confidence: confidence,
      isTestFixture: false,
      modelVersion: model.version,
    );
  }

  List<double> _extractAngles(List<Map<String, double>> points) {
    List<double> vector(int start, int end) {
      return [
        (points[end]['x'] ?? 0) - (points[start]['x'] ?? 0),
        (points[end]['y'] ?? 0) - (points[start]['y'] ?? 0),
        (points[end]['z'] ?? 0) - (points[start]['z'] ?? 0),
      ];
    }

    double angle(List<double> first, List<double> second) {
      final dot = first[0] * second[0] +
          first[1] * second[1] +
          first[2] * second[2];
      final firstMagnitude = math.sqrt(
        first[0] * first[0] +
            first[1] * first[1] +
            first[2] * first[2],
      );
      final secondMagnitude = math.sqrt(
        second[0] * second[0] +
            second[1] * second[1] +
            second[2] * second[2],
      );
      if (firstMagnitude == 0 || secondMagnitude == 0) return 0;
      final cosine =
          (dot / (firstMagnitude * secondMagnitude)).clamp(-1.0, 1.0);
      return math.acos(cosine) * 180 / math.pi;
    }

    return [
      angle(vector(0, 2), vector(2, 4)),
      angle(vector(0, 5), vector(5, 8)),
      angle(vector(0, 9), vector(9, 12)),
      angle(vector(0, 13), vector(13, 16)),
      angle(vector(0, 17), vector(17, 20)),
      angle(vector(5, 8), vector(9, 12)),
      angle(vector(9, 12), vector(13, 16)),
      angle(vector(13, 16), vector(17, 20)),
    ];
  }
}
