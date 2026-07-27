import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sinaliza_ai/data/trainer_session_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('restaura sessão válida do professor', () async {
    final store = TrainerSessionStore();
    await store.save(
      TrainerSession(
        token: 'token-seguro',
        trainerName: 'Professora Ana',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      ),
    );

    final restored = await TrainerSessionStore().restore();

    expect(restored?.token, 'token-seguro');
    expect(restored?.trainerName, 'Professora Ana');
    expect(restored?.isValid, isTrue);
  });

  test('descarta sessão expirada', () async {
    final store = TrainerSessionStore();
    await store.save(
      TrainerSession(
        token: 'token-expirado',
        trainerName: 'Professor Antigo',
        expiresAt: DateTime.now().subtract(const Duration(minutes: 1)),
      ),
    );

    expect(await TrainerSessionStore().restore(), isNull);
  });
}
