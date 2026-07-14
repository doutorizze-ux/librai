import 'package:flutter/foundation.dart';
import 'dart:html' as html;

class TtsService {
  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;

    try {
      final utterance = html.SpeechSynthesisUtterance(text);
      utterance.lang = 'pt-BR';
      html.window.speechSynthesis?.speak(utterance);
      debugPrint("[TTS Web] Falando: '$text'");
    } catch (e) {
      debugPrint("[TTS Web Error] Falha ao sintetizar áudio no navegador: $e");
    }
  }
}
