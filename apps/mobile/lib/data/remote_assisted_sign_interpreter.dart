import 'package:dio/dio.dart';

import '../domain/entities/assisted_prediction.dart';
import '../domain/interfaces/assisted_sign_interpreter.dart';
import '../platform/app_config.dart';

class RemoteAssistedSignInterpreter implements AssistedSignInterpreter {
  RemoteAssistedSignInterpreter({Dio? client})
    : _client =
          client ??
          Dio(
            BaseOptions(
              baseUrl: AppConfig.apiUrl,
              connectTimeout: const Duration(seconds: 8),
              receiveTimeout: const Duration(seconds: 12),
              sendTimeout: const Duration(seconds: 12),
              headers: const {'Content-Type': 'application/json'},
            ),
          );

  final Dio _client;

  @override
  Future<AssistedPrediction> predict(List<Map<String, dynamic>> frames) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/v1/translation/predict-assisted',
      data: {'format_version': 1, 'frames': frames},
    );
    final data = response.data;
    if (data == null || data['candidates'] is! List) {
      throw const FormatException('Resposta de reconhecimento inválida.');
    }
    final candidates = <AssistedPredictionCandidate>[];
    for (final item in data['candidates'] as List) {
      if (item is! Map) continue;
      final label = item['label']?.toString().trim() ?? '';
      final confidence = item['confidence'];
      if (label.isEmpty || confidence is! num) continue;
      candidates.add(
        AssistedPredictionCandidate(
          label: label,
          confidence: confidence.toDouble().clamp(0.0, 1.0).toDouble(),
        ),
      );
    }
    return AssistedPrediction(
      model: data['model']?.toString() ?? 'motion_tcn_v1',
      candidates: candidates,
    );
  }
}
