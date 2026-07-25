abstract interface class SpeechRecognizer {
  bool get isListening;

  Future<bool> initialize();

  Future<void> start(void Function(String text) onText);

  Future<void> stop();
}
