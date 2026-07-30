import 'package:shared_preferences/shared_preferences.dart';

import '../domain/entities/vlibras_avatar.dart';

class VlibrasAvatarPreferenceStore {
  static const _avatarKey = 'vlibras_avatar';

  Future<VlibrasAvatar> load() async {
    final preferences = await SharedPreferences.getInstance();
    final playerId = preferences.getString(_avatarKey);
    return VlibrasAvatar.fromPlayerId(playerId);
  }

  Future<void> save(VlibrasAvatar avatar) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_avatarKey, avatar.playerId);
  }
}
