import 'package:flutter/foundation.dart';
import 'dart:html' as html;
import 'app_config.dart';

class TtsService {
  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;

    try {
      final utterance = html.SpeechSynthesisUtterance(text);
      utterance.lang = 'pt-BR';
      utterance.rate = AppConfig.ttsSpeed;
      html.window.speechSynthesis?.speak(utterance);
      debugPrint("[TTS Web] Falando: '$text'");
    } catch (e) {
      debugPrint("[TTS Web Error] Falha ao sintetizar áudio no navegador: $e");
    }
  }

  void unlock() {
    try {
      final utterance = html.SpeechSynthesisUtterance(" ");
      utterance.volume = 0;
      html.window.speechSynthesis?.speak(utterance);
      debugPrint("[TTS Web] Desbloqueando SpeechSynthesis no iOS");
    } catch (e) {
      debugPrint("[TTS Web Error] Falha ao desbloquear SpeechSynthesis: $e");
    }
  }
}
