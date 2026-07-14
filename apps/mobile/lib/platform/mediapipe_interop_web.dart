import 'package:flutter/foundation.dart';
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
  bool get isWeb => true;

  void start() {
    try {
      JSMediaPipeBridge.start();
    } catch (e) {
      debugPrint("Falha ao iniciar MediaPipe JS: $e");
    }
  }

  void stop() {
    try {
      JSMediaPipeBridge.stop();
    } catch (e) {
      debugPrint("Falha ao parar MediaPipe JS: $e");
    }
  }

  bool isHandsDetected() {
    try {
      return JSMediaPipeBridge.handsDetected;
    } catch (e) {
      return false;
    }
  }

  bool isFaceDetected() {
    try {
      return JSMediaPipeBridge.faceDetected;
    } catch (e) {
      return false;
    }
  }

  bool isBodyDetected() {
    try {
      return JSMediaPipeBridge.poseDetected;
    } catch (e) {
      return false;
    }
  }

  List<Map<String, double>>? getLatestLandmarks() {
    try {
      final jsLandmarks = JSMediaPipeBridge.latestLandmarks;
      if (jsLandmarks == null) return null;
      
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
}
