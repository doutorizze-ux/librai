import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/data/trainer_session_store.dart';

class MemoryPreferences implements TrainerSessionPreferences {
  final Map<String, String> values = {};

  @override
  Future<String?> getString(String key) async => values[key];

  @override
  Future<void> remove(String key) async => values.remove(key);

  @override
  Future<void> setString(String key, String value) async {
    values[key] = value;
  }
}

void main() {
  test('restaura sessão válida do professor', () async {
    final preferences = MemoryPreferences();
    final store = TrainerSessionStore(preferences: preferences);
    await store.save(
      TrainerSession(
        token: 'token-seguro',
        trainerName: 'Professora Ana',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      ),
    );

    final restored =
        await TrainerSessionStore(preferences: preferences).restore();

    expect(restored?.token, 'token-seguro');
    expect(restored?.trainerName, 'Professora Ana');
    expect(restored?.isValid, isTrue);
  });

  test('descarta sessão expirada', () async {
    final preferences = MemoryPreferences();
    final store = TrainerSessionStore(preferences: preferences);
    await store.save(
      TrainerSession(
        token: 'token-expirado',
        trainerName: 'Professor Antigo',
        expiresAt: DateTime.now().subtract(const Duration(minutes: 1)),
      ),
    );

    expect(
      await TrainerSessionStore(preferences: preferences).restore(),
      isNull,
    );
  });
}
