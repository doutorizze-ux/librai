import 'package:speech_to_text/speech_to_text.dart' as speech;

import '../domain/interfaces/speech_recognizer.dart';

class DeviceSpeechRecognizer implements SpeechRecognizer {
  final speech.SpeechToText _engine = speech.SpeechToText();

  @override
  bool get isListening => _engine.isListening;

  @override
  Future<bool> initialize() {
    return _engine.initialize();
  }

  @override
  Future<void> start(void Function(String text) onText) async {
    await _engine.listen(
      onResult: (result) => onText(result.recognizedWords),
      localeId: 'pt_BR',
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
    );
  }

  @override
  Future<void> stop() {
    return _engine.stop();
  }
}
