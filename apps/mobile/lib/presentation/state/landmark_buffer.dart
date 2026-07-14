class LandmarkBuffer {
  final int maxFrames;
  final List<List<Map<String, double>>> _buffer = [];
  bool _isProcessing = false;

  LandmarkBuffer({this.maxFrames = 30});

  bool get isProcessing => _isProcessing;
  int get currentSize => _buffer.length;

  // Adiciona um frame de landmarks. Retorna true se adicionado, false se descartado por backpressure
  bool addFrame(List<Map<String, double>>? frameLandmarks) {
    if (_isProcessing) {
      // Backpressure: descarta o frame se o modelo estiver processando a inferência anterior
      return false;
    }

    if (frameLandmarks == null || frameLandmarks.isEmpty) {
      return false;
    }

    if (_buffer.length >= maxFrames) {
      _buffer.removeAt(0); // FIFO: Remove o frame mais antigo
    }

    _buffer.add(frameLandmarks);
    return true;
  }

  // Define o estado de processamento para habilitar/desabilitar backpressure
  void setProcessing(bool value) {
    _isProcessing = value;
  }

  // Limpa o buffer de frames
  void clear() {
    _buffer.clear();
    _isProcessing = false;
  }

  // Retorna os dados acumulados como uma lista sequencial de coordenadas (X, Y, Z)
  List<double> getFlattenedData() {
    final List<double> flatData = [];
    for (final frame in _buffer) {
      for (final point in frame) {
        flatData.add(point['x'] ?? 0.0);
        flatData.add(point['y'] ?? 0.0);
        flatData.add(point['z'] ?? 0.0);
      }
    }
    return flatData;
  }
}
