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
          final sourceVideo = html.document
              .getElementById('mediapipe-video-source') as html.VideoElement?;
          if (sourceVideo != null) {
            final container = html.DivElement()
              ..style.width = '100%'
              ..style.height = '100%'
              ..style.position = 'relative'
              ..style.overflow = 'hidden'
              ..style.backgroundColor = '#111318';

            final previewVideo = html.VideoElement()
              ..autoplay = true
              ..muted = true
              ..setAttribute('playsinline', 'true')
              ..setAttribute('aria-label', 'Imagem ao vivo da câmera');
            previewVideo.style
              ..display = 'block'
              ..width = '100%'
              ..height = '100%'
              ..objectFit = 'cover'
              ..backgroundColor = '#111318'
              ..position = 'absolute'
              ..top = '0'
              ..right = '0'
              ..bottom = '0'
              ..left = '0'
              ..opacity = '1'
              ..transform = 'scaleX(-1)'
              ..zIndex = '1';

            final oldCanvas =
                html.document.getElementById('mediapipe-overlay-canvas');
            oldCanvas?.remove();
            final canvas = html.CanvasElement()
              ..id = 'mediapipe-overlay-canvas'
              ..setAttribute('aria-hidden', 'true');
            canvas.style
              ..position = 'absolute'
              ..top = '0'
              ..right = '0'
              ..bottom = '0'
              ..left = '0'
              ..width = '100%'
              ..height = '100%'
              ..pointerEvents = 'none'
              ..zIndex = '2';

            container.children.addAll([previewVideo, canvas]);

            void attachPreviewStream() {
              final stream = sourceVideo.srcObject;
              if (stream == null) return;
              if (previewVideo.srcObject != stream) {
                previewVideo.srcObject = stream;
              }
              previewVideo.play().catchError((error) {
                debugPrint('Erro ao iniciar preview visível: $error');
              });
            }
            sourceVideo.onLoadedMetadata.listen((_) => attachPreviewStream());
            sourceVideo.onPlaying.listen((_) => attachPreviewStream());

            Future.delayed(const Duration(milliseconds: 150), () {
              attachPreviewStream();
              previewVideo.play().catchError((e) {
                debugPrint("Erro ao forçar play pós-anexo no DOM: $e");
              });
            });

            for (final delay in const [300, 700, 1500]) {
              Future.delayed(
                Duration(milliseconds: delay),
                attachPreviewStream,
              );
            }

            return container;
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

  String getTrackingQuality() {
    try {
      final b = _bridge;
      if (b == null) return 'waiting';
      return js_util.getProperty(b, 'trackingQuality')?.toString() ?? 'waiting';
    } catch (e) {
      return 'waiting';
    }
  }

  int getHandsCount() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (js_util.getProperty(b, 'handsCount') as num?)?.toInt() ?? 0;
    } catch (e) {
      return 0;
    }
  }

  double getInferenceFps() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (js_util.getProperty(b, 'inferenceFps') as num?)?.toDouble() ?? 0;
    } catch (e) {
      return 0;
    }
  }

  int getInferenceLatencyMs() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (js_util.getProperty(b, 'inferenceLatencyMs') as num?)?.toInt() ?? 0;
    } catch (e) {
      return 0;
    }
  }

  int getHandScreenRatio() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (js_util.getProperty(b, 'handScreenRatio') as num?)?.toInt() ?? 0;
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

  Map<String, dynamic>? getLatestHandFrame() {
    try {
      final b = _bridge;
      if (b == null) return null;
      final jsFrame = js_util.getProperty(b, 'latestHandFrame');
      if (jsFrame == null) return null;
      final jsHands = js_util.getProperty(jsFrame, 'hands');
      final handCount = (js_util.getProperty(jsHands, 'length') as num).toInt();
      final hands = <Map<String, dynamic>>[];
      for (var handIndex = 0; handIndex < handCount; handIndex++) {
        final jsHand = js_util.getProperty(jsHands, handIndex);
        final jsPoints = js_util.getProperty(jsHand, 'landmarks');
        final pointCount =
            (js_util.getProperty(jsPoints, 'length') as num).toInt();
        final points = <Map<String, double>>[];
        for (var pointIndex = 0; pointIndex < pointCount; pointIndex++) {
          final point = js_util.getProperty(jsPoints, pointIndex);
          points.add({
            'x': (js_util.getProperty(point, 'x') as num).toDouble(),
            'y': (js_util.getProperty(point, 'y') as num).toDouble(),
            'z': (js_util.getProperty(point, 'z') as num).toDouble(),
          });
        }
        hands.add({
          'handedness':
              js_util.getProperty(jsHand, 'handedness')?.toString() ?? 'Unknown',
          'score':
              (js_util.getProperty(jsHand, 'score') as num?)?.toDouble() ?? 0,
          'landmarks': points,
        });
      }
      return {
        'timestamp_ms':
            (js_util.getProperty(jsFrame, 'timestampMs') as num).toInt(),
        'hands': hands,
      };
    } catch (e) {
      debugPrint('Falha ao ler quadro estruturado das mãos: $e');
      return null;
    }
  }
}
