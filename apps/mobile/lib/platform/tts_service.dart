import 'package:flutter/foundation.dart';
import 'package:js/js.dart' as js;
import 'package:js/js_util.dart' as js_util;

@js.JS('speechSynthesis')
class JSSpeechSynthesis {
  external static void speak(dynamic utterance);
}

@js.JS('SpeechSynthesisUtterance')
class JSSpeechSynthesisUtterance {
  external factory JSSpeechSynthesisUtterance(String text);
  external set lang(String value);
}

class TtsService {
  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;

    if (kIsWeb) {
      try {
        final utterance = JSSpeechSynthesisUtterance(text);
        utterance.lang = 'pt-BR';
        js_util.callMethod(js_util.globalThis, 'speechSynthesis.speak', [utterance]);
        debugPrint("[TTS Web] Falando: '$text'");
      } catch (e) {
        debugPrint("[TTS Web Error] Falha ao sintetizar áudio no navegador: $e");
      }
    } else {
      // Fallback de logs nativo no Mobile para simulação de testes
      debugPrint("[TTS Mock Mobile] Falando em pt-BR: '$text'");
    }
  }
}
