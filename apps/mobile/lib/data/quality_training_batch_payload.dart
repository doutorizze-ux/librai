import '../domain/isolated_sign_label.dart';

class QualityTrainingBatchPayload {
  static Map<String, dynamic> build({
    required String signName,
    required List<List<Map<String, dynamic>>> repetitions,
    required String platform,
    String cameraFacing = 'front',
  }) {
    if (!IsolatedSignLabel.isValid(signName)) {
      throw const FormatException(
        'O treinamento de qualidade aceita uma palavra por vez.',
      );
    }
    if (repetitions.length != 5) {
      throw const FormatException(
        'O lote precisa conter exatamente cinco repetições.',
      );
    }
    return {
      'sign_name': IsolatedSignLabel.normalize(signName),
      'format_version': 3,
      'capture_context': {
        'platform': platform,
        'camera_facing': cameraFacing,
      },
      'repetitions': repetitions
          .map((frames) => {'frames': frames})
          .toList(growable: false),
    };
  }
}
