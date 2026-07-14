import 'dart:convert';
import 'package:flutter/foundation.dart';

// Condicional para importação de JS somente na web
// Para evitar erros de compilação em dispositivos móveis Android/iOS
import 'package:js/js.dart' as js;
import 'package:js/js_util.dart' as js_util;

@js.JS('sinalizaAiMediaPipe')
class JSMediaPipeBridge {
  external static bool get handsDetected;
  external static bool get faceDetected;
  external static bool get poseDetected;
  external static bool get isActive;
  external static dynamic get latestLandmarks;
  external static void start();
  external static void stop();
}

class MediaPipeService {
  bool get isWeb => kIsWeb;

  void start() {
    if (isWeb) {
      try {
        JSMediaPipeBridge.start();
      } catch (e) {
        debugPrint("Falha ao iniciar MediaPipe JS: $e");
      }
    } else {
      debugPrint("[Mock] Câmera e MediaPipe Iniciados no Mobile.");
    }
  }

  void stop() {
    if (isWeb) {
      try {
        JSMediaPipeBridge.stop();
      } catch (e) {
        debugPrint("Falha ao parar MediaPipe JS: $e");
      }
    } else {
      debugPrint("[Mock] Câmera e MediaPipe Parados no Mobile.");
    }
  }

  bool isHandsDetected() {
    if (isWeb) {
      try {
        return JSMediaPipeBridge.handsDetected;
      } catch (e) {
        return false;
      }
    }
    return true; // Mock sempre detectado no Mobile para testes
  }

  bool isFaceDetected() {
    if (isWeb) {
      try {
        return JSMediaPipeBridge.faceDetected;
      } catch (e) {
        return false;
      }
    }
    return true;
  }

  bool isBodyDetected() {
    if (isWeb) {
      try {
        return JSMediaPipeBridge.poseDetected;
      } catch (e) {
        return false;
      }
    }
    return true;
  }

  // Retorna uma lista de landmarks contendo chaves x, y, z
  List<Map<String, double>>? getLatestLandmarks() {
    if (isWeb) {
      try {
        final jsLandmarks = JSMediaPipeBridge.latestLandmarks;
        if (jsLandmarks == null) return null;
        
        // Conversão de JS Array para Dart List
        final List<Map<String, double>> result = [];
        final int length = js_util.getProperty(jsLandmarks, 'length') as int;
        
        for (int i = 0; i < length; i++) {
          final item = js_util.getProperty(jsLandmarks, i);
          final double x = js_util.getProperty(item, 'x') as double;
          final double y = js_util.getProperty(item, 'y') as double;
          final double z = js_util.getProperty(item, 'z') as double;
          result.add({'x': x, 'y': y, 'z': z});
        }
        return result;
      } catch (e) {
        return null;
      }
    }
    
    // Gerar landmarks de teste dinâmicos para celular/teste
    // Move os pontos levemente no tempo simulando um sinalizador
    final int now = DateTime.now().millisecondsSinceEpoch;
    final double offset = (now % 2000) / 2000.0;
    return [
      {'x': 0.5 + 0.1 * offset, 'y': 0.6, 'z': 0.0},
      {'x': 0.52, 'y': 0.61 + 0.05 * offset, 'z': 0.0},
    ];
  }
}
