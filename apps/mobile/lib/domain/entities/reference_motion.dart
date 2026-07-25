class ReferencePoint {
  const ReferencePoint(this.x, this.y, this.z);

  final double x;
  final double y;
  final double z;
}

class ReferenceMotionFrame {
  const ReferenceMotionFrame({
    required this.time,
    required this.body,
    required this.leftHand,
    required this.rightHand,
  });

  final double time;
  final Map<String, ReferencePoint> body;
  final List<ReferencePoint> leftHand;
  final List<ReferencePoint> rightHand;
}

class ReferenceMotion {
  const ReferenceMotion({
    required this.label,
    required this.fps,
    required this.duration,
    required this.frames,
  });

  final String label;
  final int fps;
  final Duration duration;
  final List<ReferenceMotionFrame> frames;
}
