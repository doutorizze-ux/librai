import 'package:flutter/foundation.dart';
import 'dart:js' as js;
import 'dart:ui_web' as ui_web;
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

class MediaPipeService {
  bool get isWeb => true;

  void registerVideoView() {
    try {
      ui_web.platformViewRegistry.registerViewFactory(
        'mediapipe-video-view',
        (int viewId) {
          final container = html.DivElement()
            ..style.position = 'relative'
            ..style.width = '100%'
            ..style.height = '100%'
            ..style.overflow = 'hidden';

          final video = html.document.getElementById('mediapipe-video-source') as html.VideoElement?;
          if (video != null) {
            video.style.display = 'block';
            video.style.width = '100%';
            video.style.height = '100%';
            video.style.objectFit = 'cover';
            video.style.position = 'absolute';
            video.style.top = '0';
            video.style.left = '0';
            video.style.opacity = '1';
            video.style.transform = 'scaleX(-1)';
            container.children.add(video);

            Future.delayed(const Duration(milliseconds: 150), () {
              video.play().catchError((e) {
                debugPrint("Erro ao forçar play pós-anexo no DOM: $e");
              });
            });
          }

          var canvas = html.document.getElementById('mediapipe-overlay-canvas') as html.CanvasElement?;
          if (canvas == null) {
            canvas = html.CanvasElement()
              ..id = 'mediapipe-overlay-canvas'
              ..style.position = 'absolute'
              ..style.top = '0'
              ..style.left = '0'
              ..style.width = '100%'
              ..style.height = '100%'
              ..style.objectFit = 'cover'
              ..style.pointerEvents = 'none'
              ..style.transform = 'scaleX(-1)';
          } else {
            canvas.style.position = 'absolute';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.objectFit = 'cover';
            canvas.style.pointerEvents = 'none';
            canvas.style.transform = 'scaleX(-1)';
          }
          container.children.add(canvas);

          return container;
        },
      );
    } catch (e) {
      debugPrint("Erro ao registrar factory de video web: $e");
    }
  }

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
    return true; // Ignorado no Web para estabilidade de memória e CPU
  }

  bool isBodyDetected() {
    return true; // Ignorado no Web para estabilidade de memória e CPU
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
