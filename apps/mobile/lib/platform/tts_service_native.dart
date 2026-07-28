import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

import 'app_config.dart';

class TtsService {
  final FlutterTts _engine = FlutterTts();

  Future<void> speak(String text) async {
    final content = text.trim();
    if (content.isEmpty) return;
    try {
      await _engine.stop();
      await _engine.setLanguage('pt-BR');
      await _engine.setSpeechRate(
        (AppConfig.ttsSpeed * 0.5).clamp(0.1, 1.0).toDouble(),
      );
      await _engine.speak(content);
    } catch (error) {
      debugPrint('[TTS nativo] Falha ao sintetizar voz: $error');
    }
  }

  void unlock() {}
}
