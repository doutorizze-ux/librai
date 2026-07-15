import 'package:flutter/foundation.dart';

class MediaPipeService {
  bool get isWeb => false;

  void registerVideoView() {}

  void start() {
    debugPrint("[Mock Stub] Câmera e MediaPipe Iniciados.");
  }

  void stop() {
    debugPrint("[Mock Stub] Câmera e MediaPipe Parados.");
  }

  bool isHandsDetected() {
    return true; // Mock sempre ativo para facilitação de testes nativos
  }

  bool isFaceDetected() {
    return true;
  }

  bool isBodyDetected() {
    return true;
  }

  List<Map<String, double>>? getLatestLandmarks() {
    // Retorna landmarks de teste dinâmicos
    final int now = DateTime.now().millisecondsSinceEpoch;
    final double offset = (now % 2000) / 2000.0;
    return [
      {'x': 0.5 + 0.1 * offset, 'y': 0.6, 'z': 0.0},
      {'x': 0.52, 'y': 0.61 + 0.05 * offset, 'z': 0.0},
    ];
  }
}
