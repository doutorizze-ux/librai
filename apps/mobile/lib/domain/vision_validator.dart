enum VisionState {
  waitingPerson,
  adjustFraming,
  stepBack,
  stepCloser,
  insufficientLighting,
  handsOutOfFrame,
  faceOutOfFrame,
  ok
}

class VisionValidator {
  // Área ideal de enquadramento (percentual de 0 a 1)
  static const double minX = 0.15;
  static const double maxX = 0.85;
  static const double minY = 0.15;
  static const double maxY = 0.85;

  // Avalia o posicionamento geométrico dos landmarks
  static VisionState validateFraming(List<Map<String, double>>? landmarks, bool faceDetected) {
    if (landmarks == null || landmarks.isEmpty) {
      return VisionState.waitingPerson;
    }
    
    if (!faceDetected) {
      return VisionState.faceOutOfFrame;
    }

    double sumX = 0;
    double sumY = 0;
    double minLandmarkX = 1.0;
    double maxLandmarkX = 0.0;

    for (final point in landmarks) {
      final x = point['x'] ?? 0.5;
      final y = point['y'] ?? 0.5;

      sumX += x;
      sumY += y;

      if (x < minLandmarkX) minLandmarkX = x;
      if (x > maxLandmarkX) maxLandmarkX = x;

      // Se qualquer ponto crítico ultrapassar a borda limite extrema
      if (x < 0.02 || x > 0.98 || y < 0.02 || y > 0.98) {
        return VisionState.handsOutOfFrame;
      }
    }

    final double avgX = sumX / landmarks.length;
    final double avgY = sumY / landmarks.length;
    final double spreadX = maxLandmarkX - minLandmarkX;

    // Se o espalhamento das coordenadas for muito pequeno (sinalizador muito longe)
    if (spreadX < 0.10) {
      return VisionState.stepCloser;
    }

    // Se o espalhamento for muito grande (muito próximo)
    if (spreadX > 0.65) {
      return VisionState.stepBack;
    }

    // Se a posição média estiver fora da zona ideal central
    if (avgX < minX || avgX > maxX || avgY < minY || avgY > maxY) {
      return VisionState.adjustFraming;
    }

    return VisionState.ok;
  }
}
