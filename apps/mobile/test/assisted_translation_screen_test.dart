import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/entities/assisted_prediction.dart';
import 'package:sinaliza_ai/domain/interfaces/assisted_sign_interpreter.dart';
import 'package:sinaliza_ai/platform/mediapipe_interop.dart';
import 'package:sinaliza_ai/presentation/screens/assisted_translation_screen.dart';

class _FakeInterpreter implements AssistedSignInterpreter {
  @override
  Future<AssistedPrediction> predict(List<Map<String, dynamic>> frames) async {
    expect(frames.length, greaterThanOrEqualTo(12));
    return const AssistedPrediction(
      model: 'motion_tcn_v1',
      candidates: [
        AssistedPredictionCandidate(label: 'BOM', confidence: 0.7),
        AssistedPredictionCandidate(label: 'TARDE', confidence: 0.2),
        AssistedPredictionCandidate(label: 'NOITE', confidence: 0.08),
      ],
    );
  }
}

class _FakeVisionService extends MediaPipeService {
  int _revision = 0;

  @override
  int getLandmarkRevision() => ++_revision;

  @override
  Map<String, dynamic> getLatestHandFrame() {
    return {
      'timestamp_ms': 1000 + _revision * 33,
      'hands': [
        {
          'handedness': 'Left',
          'score': 0.99,
          'landmarks': [
            for (var index = 0; index < 21; index++)
              {
                'x': 0.2 + index / 100,
                'y': 0.3 + index / 200,
                'z': index / 1000,
              },
          ],
        },
      ],
    };
  }

  @override
  void registerVideoView() {}

  @override
  void start() {}

  @override
  void stop() {}
}

void main() {
  testWidgets('captura explícita mostra as três opções do modelo', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AssistedTranslationScreen(
          interpreter: _FakeInterpreter(),
          visionService: _FakeVisionService(),
        ),
      ),
    );

    await tester.tap(find.text('Começar captura'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('CAPTURANDO'), findsOneWidget);

    await tester.tap(find.text('Finalizar sinal'));
    await tester.pumpAndSettle();

    expect(find.text('Bom'), findsOneWidget);
    expect(find.text('Tarde'), findsOneWidget);
    expect(find.text('Noite'), findsOneWidget);
    expect(find.text('Capturar próximo sinal'), findsOneWidget);
  });
}
