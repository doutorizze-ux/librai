import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sinaliza_ai/data/training_draft_store.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('preserva uma repetição pendente após reiniciar a tela', () async {
    final store = TrainingDraftStore();
    final repetition = PendingTrainingRepetition(
      captureId: 'capture_1234567890',
      trainerName: 'Professora Ana',
      signName: 'OLÁ',
      platform: 'ios',
      cameraFacing: 'front',
      frames: [
        {
          'timestamp_ms': 1000,
          'hands': [
            {
              'handedness': 'Right',
              'score': 0.99,
              'landmarks': [
                {'x': 0.1, 'y': 0.2, 'z': 0.3},
              ],
            },
          ],
        },
      ],
    );

    await store.save(repetition);
    final restored = await TrainingDraftStore().restore('Professora Ana');

    expect(restored, isNotNull);
    expect(restored!.captureId, repetition.captureId);
    expect(restored.signName, 'OLÁ');
    expect(restored.frames, hasLength(1));
    expect(restored.frames.first['timestamp_ms'], 1000);
  });

  test('não entrega a captura pendente para outro professor', () async {
    final store = TrainingDraftStore();
    await store.save(
      const PendingTrainingRepetition(
        captureId: 'capture_1234567890',
        trainerName: 'Professora Ana',
        signName: 'OLÁ',
        platform: 'web',
        cameraFacing: 'front',
        frames: [
          {'timestamp_ms': 1000, 'hands': []},
        ],
      ),
    );

    expect(await store.restore('Professor Bruno'), isNull);
    expect(await store.restore('Professora Ana'), isNotNull);
  });

  test('remove a repetição somente após confirmação do servidor', () async {
    final store = TrainingDraftStore();
    await store.save(
      const PendingTrainingRepetition(
        captureId: 'capture_1234567890',
        trainerName: 'Professora Ana',
        signName: 'OLÁ',
        platform: 'web',
        cameraFacing: 'front',
        frames: [
          {'timestamp_ms': 1000, 'hands': []},
        ],
      ),
    );

    await store.clear();

    expect(await store.restore('Professora Ana'), isNull);
  });
}
