import 'package:flutter/foundation.dart';
import 'dart:js' as js;

class MediaPipeService {
  bool get isWeb => true;

  // Obter o objeto da ponte global do JS
  js.JsObject? get _bridge {
    try {
      if (js.context.hasProperty('sinalizaAiMediaPipe')) {
        final bridgeObj = js.context['sinalizaAiMediaPipe'];
        if (bridgeObj != null) {
          return bridgeObj as js.JsObject;
        }
      }
    } catch (e) {
      debugPrint("Erro ao acessar sinalizaAiMediaPipe: $e");
    }
    return null;
  }

  void start() {
    try {
      _bridge?.callMethod('start');
    } catch (e) {
      debugPrint("Falha ao iniciar MediaPipe JS: $e");
    }
  }

  void stop() {
    try {
      _bridge?.callMethod('stop');
    } catch (e) {
      debugPrint("Falha ao parar MediaPipe JS: $e");
    }
  }

  bool isHandsDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      return b['handsDetected'] as bool? ?? false;
    } catch (e) {
      return false;
    }
  }

  bool isFaceDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      return b['faceDetected'] as bool? ?? false;
    } catch (e) {
      return false;
    }
  }

  bool isBodyDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      return b['poseDetected'] as bool? ?? false;
    } catch (e) {
      return false;
    }
  }

  List<Map<String, double>>? getLatestLandmarks() {
    try {
      final b = _bridge;
      if (b == null) return null;
      
      final jsLandmarks = b['latestLandmarks'] as js.JsArray?;
      if (jsLandmarks == null) return null;
      
      final List<Map<String, double>> result = [];
      for (int i = 0; i < jsLandmarks.length; i++) {
        final item = jsLandmarks[i] as js.JsObject;
        final double x = (item['x'] as num).toDouble();
        final double y = (item['y'] as num).toDouble();
        final double z = (item['z'] as num).toDouble();
        result.add({'x': x, 'y': y, 'z': z});
      }
      return result;
    } catch (e) {
      return null;
    }
  }
}
