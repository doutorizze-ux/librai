import 'package:flutter/foundation.dart';

class TtsService {
  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;
    debugPrint("[TTS Stub] Falando: '$text'");
  }

  void unlock() {}
}
