import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sinaliza_ai/data/vlibras_avatar_preference_store.dart';
import 'package:sinaliza_ai/domain/entities/vlibras_avatar.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('uses Hozana when no avatar was saved', () async {
    final store = VlibrasAvatarPreferenceStore();

    expect(await store.load(), VlibrasAvatar.hozana);
  });

  test('saves and restores the selected official avatar', () async {
    final store = VlibrasAvatarPreferenceStore();

    await store.save(VlibrasAvatar.icaro);

    expect(await store.load(), VlibrasAvatar.icaro);
  });
}
