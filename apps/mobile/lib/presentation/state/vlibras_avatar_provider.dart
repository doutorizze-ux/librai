import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/vlibras_avatar_preference_store.dart';
import '../../domain/entities/vlibras_avatar.dart';

final vlibrasAvatarPreferenceStoreProvider =
    Provider<VlibrasAvatarPreferenceStore>((ref) {
  return VlibrasAvatarPreferenceStore();
});

final vlibrasAvatarProvider =
    StateNotifierProvider<VlibrasAvatarController, VlibrasAvatar>((ref) {
  return VlibrasAvatarController(
    ref.watch(vlibrasAvatarPreferenceStoreProvider),
  );
});

class VlibrasAvatarController extends StateNotifier<VlibrasAvatar> {
  VlibrasAvatarController(this._store) : super(VlibrasAvatar.hozana) {
    unawaited(_restore());
  }

  final VlibrasAvatarPreferenceStore _store;
  bool _changedByUser = false;

  Future<void> _restore() async {
    try {
      final savedAvatar = await _store.load();
      if (!_changedByUser) state = savedAvatar;
    } catch (_) {
      // Mantém Hozana como padrão quando o armazenamento não está disponível.
    }
  }

  Future<void> select(VlibrasAvatar avatar) async {
    _changedByUser = true;
    state = avatar;
    try {
      await _store.save(avatar);
    } catch (_) {
      // A escolha continua válida durante a sessão mesmo sem persistência.
    }
  }
}
