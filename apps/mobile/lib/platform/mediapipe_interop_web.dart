// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'dart:ui_web' as ui_web;
import 'dart:html' as html;

import 'package:flutter/foundation.dart';

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

            final oldCanvas =
                html.document.getElementById('mediapipe-overlay-canvas');
            oldCanvas?.remove();
            final canvas = html.CanvasElement()
              ..id = 'mediapipe-overlay-canvas'
              ..setAttribute('role', 'img')
              ..setAttribute(
                'aria-label',
                'Imagem ao vivo da câmera com rastreamento das mãos',
              );
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

            // A prévia usa o vídeo nativo do navegador. O MediaPipe desenha
            // somente os landmarks no canvas transparente acima dele. Assim,
            // uma inferência mais demorada não congela a imagem da câmera.
            sourceVideo.style
              ..display = 'block'
              ..position = 'absolute'
              ..top = '0'
              ..right = '0'
              ..bottom = '0'
              ..left = '0'
              ..width = '100%'
              ..height = '100%'
              ..opacity = '1'
              ..zIndex = '1'
              ..transform = 'scaleX(-1)';
            sourceVideo.style.setProperty('object-fit', 'cover');
            sourceVideo.style.setProperty('will-change', 'transform');
            sourceVideo.style.setProperty('backface-visibility', 'hidden');

            container.children.add(sourceVideo);
            container.children.add(canvas);

            return container;
          }
          return html.VideoElement();
        },
      );
    } catch (e) {
      debugPrint("Erro ao registrar factory de video web: $e");
    }
  }

  JSObject? get _bridge {
    try {
      final value = globalContext.getProperty<JSAny?>(
        'sinalizaAiMediaPipe'.toJS,
      );
      if (value != null && value.isA<JSObject>()) {
        return value as JSObject;
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
        b.callMethod<JSAny?>('start'.toJS);
      }
    } catch (e) {
      debugPrint("Falha ao iniciar MediaPipe JS: $e");
    }
  }

  void stop() {
    try {
      final b = _bridge;
      if (b != null) {
        b.callMethod<JSAny?>('stop'.toJS);
      }
    } catch (e) {
      debugPrint("Falha ao parar MediaPipe JS: $e");
    }
  }

  void setCaptureMode(String mode) {
    try {
      final b = _bridge;
      if (b != null) {
        b.callMethod<JSAny?>('setCaptureMode'.toJS, mode.toJS);
      }
    } catch (e) {
      debugPrint("Falha ao selecionar modo do MediaPipe JS: $e");
    }
  }

  bool isHandsDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      final val = b.getProperty<JSAny?>('handsDetected'.toJS)?.dartify();
      return val == true;
    } catch (e) {
      return false;
    }
  }

  bool isFaceDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      return b.getProperty<JSAny?>('faceDetected'.toJS)?.dartify() == true;
    } catch (e) {
      return false;
    }
  }

  bool isBodyDetected() {
    try {
      final b = _bridge;
      if (b == null) return false;
      return b.getProperty<JSAny?>('poseDetected'.toJS)?.dartify() == true;
    } catch (e) {
      return false;
    }
  }

  int getLandmarkRevision() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (b.getProperty<JSAny?>('landmarkRevision'.toJS)?.dartify() as num?)
              ?.toInt() ??
          0;
    } catch (e) {
      return 0;
    }
  }

  String getTrackingQuality() {
    try {
      final b = _bridge;
      if (b == null) return 'waiting';
      return b
              .getProperty<JSAny?>('trackingQuality'.toJS)
              ?.dartify()
              ?.toString() ??
          'waiting';
    } catch (e) {
      return 'waiting';
    }
  }

  int getHandsCount() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (b.getProperty<JSAny?>('handsCount'.toJS)?.dartify() as num?)
              ?.toInt() ??
          0;
    } catch (e) {
      return 0;
    }
  }

  double getInferenceFps() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (b.getProperty<JSAny?>('inferenceFps'.toJS)?.dartify() as num?)
              ?.toDouble() ??
          0;
    } catch (e) {
      return 0;
    }
  }

  int getInferenceLatencyMs() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (b.getProperty<JSAny?>('inferenceLatencyMs'.toJS)?.dartify()
                  as num?)
              ?.toInt() ??
          0;
    } catch (e) {
      return 0;
    }
  }

  int getHandScreenRatio() {
    try {
      final b = _bridge;
      if (b == null) return 0;
      return (b.getProperty<JSAny?>('handScreenRatio'.toJS)?.dartify() as num?)
              ?.toInt() ??
          0;
    } catch (e) {
      return 0;
    }
  }

  List<Map<String, double>>? getLatestLandmarks() {
    try {
      final b = _bridge;
      if (b == null) return null;

      final raw = b.getProperty<JSAny?>('latestLandmarks'.toJS)?.dartify();
      if (raw is! List || raw.isEmpty) return null;

      final result = <Map<String, double>>[];
      for (final item in raw) {
        if (item is! Map) continue;
        final x = item['x'];
        final y = item['y'];
        final z = item['z'];
        if (x is num && y is num && z is num) {
          result.add({
            'x': x.toDouble(),
            'y': y.toDouble(),
            'z': z.toDouble(),
          });
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
      final rawFrame = b.getProperty<JSAny?>('latestHandFrame'.toJS)?.dartify();
      if (rawFrame is! Map) return null;
      final rawHands = rawFrame['hands'];
      final timestamp = rawFrame['timestampMs'];
      if (rawHands is! List || timestamp is! num) return null;
      final hands = <Map<String, dynamic>>[];
      for (final rawHand in rawHands) {
        if (rawHand is! Map) continue;
        final rawPoints = rawHand['landmarks'];
        if (rawPoints is! List) continue;
        final points = <Map<String, double>>[];
        for (final point in rawPoints) {
          if (point is! Map) continue;
          final x = point['x'];
          final y = point['y'];
          final z = point['z'];
          if (x is! num || y is! num || z is! num) continue;
          points.add({
            'x': x.toDouble(),
            'y': y.toDouble(),
            'z': z.toDouble(),
          });
        }
        if (points.length != 21) continue;
        final score = rawHand['score'];
        hands.add({
          'handedness': rawHand['handedness']?.toString() ?? 'Unknown',
          'score': score is num ? score.toDouble() : 0.0,
          'landmarks': points,
        });
      }
      return {
        'timestamp_ms': timestamp.toInt(),
        'hands': hands,
      };
    } catch (e) {
      debugPrint('Falha ao ler quadro estruturado das mãos: $e');
      return null;
    }
  }

  Map<String, dynamic>? getLatestHolisticFrame() {
    try {
      final b = _bridge;
      if (b == null) return null;
      final raw = b.getProperty<JSAny?>('latestHolisticFrame'.toJS)?.dartify();
      if (raw is! Map) return null;
      final timestamp = raw['timestampMs'];
      final rawHands = raw['hands'];
      final rawPose = raw['pose'];
      final rawExpression = raw['expression'];
      if (timestamp is! num ||
          rawHands is! List ||
          rawPose is! Map ||
          rawExpression is! Map) {
        return null;
      }

      final hands = <Map<String, dynamic>>[];
      for (final rawHand in rawHands) {
        if (rawHand is! Map) continue;
        final points = _parsePoints(rawHand['landmarks']);
        if (points.length != 21) continue;
        final score = rawHand['score'];
        hands.add({
          'handedness': rawHand['handedness']?.toString() ?? 'Unknown',
          'score': score is num ? score.toDouble() : 0.0,
          'landmarks': points,
        });
      }

      final posePoints = _parsePoints(rawPose['landmarks']);
      if (hands.isEmpty || posePoints.length != 13) return null;
      double? number(String key) {
        final value = rawExpression[key];
        return value is num ? value.toDouble() : null;
      }

      final mouthOpen = number('mouth_open');
      final mouthWidth = number('mouth_width');
      final leftBrow = number('left_brow');
      final rightBrow = number('right_brow');
      if (mouthOpen == null ||
          mouthWidth == null ||
          leftBrow == null ||
          rightBrow == null) {
        return null;
      }
      return {
        'timestamp_ms': timestamp.toInt(),
        'hands': hands,
        'pose': {'landmarks': posePoints},
        'expression': {
          'mouth_open': mouthOpen,
          'mouth_width': mouthWidth,
          'left_brow': leftBrow,
          'right_brow': rightBrow,
        },
      };
    } catch (e) {
      debugPrint('Falha ao ler quadro holístico: $e');
      return null;
    }
  }

  List<Map<String, double>> _parsePoints(Object? rawPoints) {
    if (rawPoints is! List) return const [];
    final points = <Map<String, double>>[];
    for (final point in rawPoints) {
      if (point is! Map) continue;
      final x = point['x'];
      final y = point['y'];
      final z = point['z'];
      if (x is num && y is num && z is num) {
        points.add({
          'x': x.toDouble(),
          'y': y.toDouble(),
          'z': z.toDouble(),
        });
      }
    }
    return points;
  }
}
