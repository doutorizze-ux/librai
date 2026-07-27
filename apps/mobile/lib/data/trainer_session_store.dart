import 'package:shared_preferences/shared_preferences.dart';

class TrainerSession {
  const TrainerSession({
    required this.token,
    required this.trainerName,
    required this.expiresAt,
  });

  final String token;
  final String trainerName;
  final DateTime expiresAt;

  bool get isValid => expiresAt.isAfter(DateTime.now());
}

class TrainerSessionStore {
  static const _tokenKey = 'librai_trainer_token';
  static const _nameKey = 'librai_trainer_name';
  static const _expiresAtKey = 'librai_trainer_expires_at';

  final SharedPreferencesAsync _preferences = SharedPreferencesAsync();

  Future<TrainerSession?> restore() async {
    final token = await _preferences.getString(_tokenKey);
    final name = await _preferences.getString(_nameKey);
    final expiresAtRaw = await _preferences.getString(_expiresAtKey);
    final expiresAt =
        expiresAtRaw == null ? null : DateTime.tryParse(expiresAtRaw);
    if (token == null || name == null || expiresAt == null) return null;
    final session = TrainerSession(
      token: token,
      trainerName: name,
      expiresAt: expiresAt,
    );
    if (!session.isValid) {
      await clear();
      return null;
    }
    return session;
  }

  Future<void> save(TrainerSession session) async {
    await _preferences.setString(_tokenKey, session.token);
    await _preferences.setString(_nameKey, session.trainerName);
    await _preferences.setString(
      _expiresAtKey,
      session.expiresAt.toIso8601String(),
    );
  }

  Future<void> clear() async {
    await _preferences.remove(_tokenKey);
    await _preferences.remove(_nameKey);
    await _preferences.remove(_expiresAtKey);
  }
}
