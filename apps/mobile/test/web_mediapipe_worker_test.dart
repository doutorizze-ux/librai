import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('hand inference runs outside the browser UI thread', () {
    final index = File('web/index.html').readAsStringSync();
    final worker = File('web/mediapipe-hand-worker.js').readAsStringSync();

    expect(index, contains('new Worker('));
    expect(index, contains('requestVideoFrameCallback'));
    expect(index, contains('createImageBitmap'));
    expect(index, contains('frameInFlight'));
    expect(index, isNot(contains('await hands.send')));

    expect(worker, contains('HandLandmarker.createFromOptions'));
    expect(worker, contains('importScripts('));
    expect(worker, contains('detectForVideo(bitmap, timestampMs)'));
    expect(worker, contains('numHands: 2'));
    expect(worker, contains('bitmap.close()'));
  });

  test('teacher mode captures hands pose and dynamic expression in a worker',
      () {
    final index = File('web/index.html').readAsStringSync();
    final worker = File('web/mediapipe-holistic-worker.js').readAsStringSync();

    expect(index, contains("captureMode: 'hands'"));
    expect(index, contains("self.setCaptureMode = function(mode)"));
    expect(index, contains('mediapipe-holistic-worker.js'));
    expect(index, contains('latestHolisticFrame'));

    expect(worker, contains('HolisticLandmarker.createFromOptions'));
    expect(worker, contains('result.leftHandLandmarks'));
    expect(worker, contains('result.rightHandLandmarks'));
    expect(worker, contains('result.poseLandmarks'));
    expect(worker, contains('result.faceLandmarks'));
    expect(worker, contains('POSE_INDICES'));
    expect(worker, contains('dynamicExpression'));
    expect(worker, contains('outputFaceBlendshapes: false'));
    expect(worker, contains('bitmap.close()'));
  });

  test('translator enables holistic capture before starting the camera', () {
    final screen = File(
      'lib/presentation/screens/translation_screen.dart',
    ).readAsStringSync();

    final holistic = screen.indexOf("setCaptureMode('holistic')");
    final start = screen.indexOf('_visionService.start()');
    expect(holistic, greaterThanOrEqualTo(0));
    expect(start, greaterThan(holistic));
  });
}
