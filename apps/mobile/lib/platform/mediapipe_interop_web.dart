// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'package:flutter/foundation.dart';
import 'dart:js_util' as js_util;
import 'dart:ui_web' as ui_web;
import 'dart:html' as html;

class MediaPipeService {
  bool get isWeb => true;

  void registerVideoView() {
    try {
      ui_web.platformViewRegistry.registerViewFactory(
        'mediapipe-video-view',
        (int viewId) {
          final video = html.document.getElementById('mediapipe-video-source') as html.VideoElement?;
          if (video != null) {
            video.style.display = 'block';
            video.style.width = '100%';
            video.style.height = '100%';
            // A interface usa a mesma proporção 16:9 solicitada à câmera.
            // Assim "cover" preenche o quadro sem as grandes faixas pretas.
            video.style.objectFit = 'cover';
            video.style.backgroundColor = '#111318';
            video.style.position = 'static';
            video.style.opacity = '1';
            video.style.transform = 'scaleX(-1)';
            
            // Forçar a reprodução após o elemento ser re-anexado no DOM do Flutter
            Future.delayed(const Duration(milliseconds: 150), () {
              video.play().catchError((e) {
                debugPrint("Erro ao forçar play pós-anexo no DOM: $e");
              });
            });
            
            return video;
          }
          return html.VideoElement();
        },
      );
    } catch (e) {
      debugPrint("Erro ao registrar factory de video web: $e");
    }
  }

  // Obter o objeto da ponte global do JS usando js_util seguro
  dynamic get _bridge {
    try {
      if (js_util.hasProperty(html.window, 'sinalizaAiMediaPipe')) {
        return js_util.getProperty(html.window, 'sinalizaAiMediaPipe');
      }
    } catch (e) {
      debugPrint("Erro ao acessar sinalizaAiMediaPipe: $e");
    }
    return null;
  }

  void start() {
    try {
      final b = _bridge;
      if (b != null) {
        js_util.callMethod(b, 'start', []);
      }
    } catch (e) {
      debugPrint("Falha ao iniciar MediaPipe JS: $e");
    }
  }

  void stop() {
    try {
      final b = _bridge;
      if (b != null) {
        js_util.callMethod(b, 'stop', []);
      }
    } catch (e) {
      debugPrint("Falha ao parar MediaPipe JS: $e");
    }
  }

  bool isHandsDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      final val = js_util.getProperty(b, 'handsDetected');
      return val == true;
    } catch (e) {
      return false;
    }
  }

  bool isFaceDetected() {
    return true; // Ignorado no Web para estabilidade de memória e CPU
  }

  bool isBodyDetected() {
    return true; // Ignorado no Web para estabilidade de memória e CPU
  }

  int getLandmarkRevision() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (js_util.getProperty(b, 'landmarkRevision') as num?)?.toInt() ?? 0;
    } catch (e) {
      return 0;
    }
  }

  List<Map<String, double>>? getLatestLandmarks() {
    try {
      final b = _bridge;
      if (b == null) return null;
      
      final jsLandmarks = js_util.getProperty(b, 'latestLandmarks');
      if (jsLandmarks == null) return null;
      
      final length = js_util.getProperty(jsLandmarks, 'length') as int?;
      if (length == null || length == 0) return null;

      final List<Map<String, double>> result = [];
      for (int i = 0; i < length; i++) {
        final item = js_util.getProperty(jsLandmarks, i);
        if (item != null) {
          final double x = (js_util.getProperty(item, 'x') as num).toDouble();
          final double y = (js_util.getProperty(item, 'y') as num).toDouble();
          final double z = (js_util.getProperty(item, 'z') as num).toDouble();
          result.add({'x': x, 'y': y, 'z': z});
        }
      }
      return result;
    } catch (e) {
      return null;
    }
  }
}
