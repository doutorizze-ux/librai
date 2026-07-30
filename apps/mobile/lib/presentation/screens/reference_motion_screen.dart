import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/reference_motion.dart';
import '../state/reference_catalog_providers.dart';

class ReferenceMotionScreen extends ConsumerWidget {
  const ReferenceMotionScreen({
    required this.label,
    super.key,
  });

  final String label;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final motion = ref.watch(referenceMotionProvider(label));
    return Scaffold(
      appBar: AppBar(title: Text(label.replaceAll('_', ' '))),
      body: motion.when(
        loading: () => const Center(
          child: CircularProgressIndicator(
            semanticsLabel: 'Carregando demonstração do sinal',
          ),
        ),
        error: (error, stackTrace) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.animation_outlined, size: 56),
                const SizedBox(height: 16),
                const Text(
                  'A demonstração visual deste sinal ainda está sendo preparada.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () => ref.invalidate(
                    referenceMotionProvider(label),
                  ),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Tentar novamente'),
                ),
              ],
            ),
          ),
        ),
        data: (data) => ReferenceMotionPlayer(motion: data),
      ),
    );
  }
}

class ReferenceMotionPlayer extends StatefulWidget {
  const ReferenceMotionPlayer({
    required this.motion,
    this.compact = false,
    this.loop = true,
    this.onCompleted,
    super.key,
  });

  final ReferenceMotion motion;
  final bool compact;
  final bool loop;
  final VoidCallback? onCompleted;

  @override
  State<ReferenceMotionPlayer> createState() => _ReferenceMotionPlayerState();
}

class _ReferenceMotionPlayerState extends State<ReferenceMotionPlayer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.motion.duration,
    );
    _controller.addStatusListener((status) {
      if (status == AnimationStatus.completed) {
        widget.onCompleted?.call();
      }
    });
    if (widget.loop) {
      _controller.repeat();
    } else {
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _togglePlayback() {
    setState(() {
      if (_controller.isAnimating) {
        _controller.stop();
      } else {
        if (_controller.isCompleted) _controller.reset();
        widget.loop ? _controller.repeat() : _controller.forward();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        if (widget.compact)
          AspectRatio(
            aspectRatio: 0.9,
            child: _motionCanvas(theme),
          )
        else
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: _motionCanvas(theme),
            ),
          ),
        if (!widget.compact)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _togglePlayback,
                    icon: Icon(
                      _controller.isAnimating ? Icons.pause : Icons.play_arrow,
                    ),
                    label: Text(
                      _controller.isAnimating ? 'Pausar' : 'Reproduzir',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                IconButton.filledTonal(
                  tooltip: 'Repetir desde o início',
                  onPressed: () {
                    _controller.reset();
                    widget.loop
                        ? _controller.repeat()
                        : _controller.forward();
                  },
                  icon: const Icon(Icons.replay),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _motionCanvas(ThemeData theme) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xFF111116),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Semantics(
        image: true,
        label:
            'Demonstração animada do sinal ${widget.motion.label.replaceAll('_', ' ')}',
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, child) {
            final frameIndex = math.min(
              widget.motion.frames.length - 1,
              (_controller.value * widget.motion.frames.length).floor(),
            );
            return CustomPaint(
              painter: _MotionPainter(
                frame: widget.motion.frames[frameIndex],
                color: theme.colorScheme.primaryContainer,
              ),
              child: const SizedBox.expand(),
            );
          },
        ),
      ),
    );
  }
}

class _MotionPainter extends CustomPainter {
  _MotionPainter({
    required this.frame,
    required this.color,
  });

  final ReferenceMotionFrame frame;
  final Color color;

  static const _handConnections = [
    [0, 1], [1, 2], [2, 3], [3, 4],
    [0, 5], [5, 6], [6, 7], [7, 8],
    [0, 9], [9, 10], [10, 11], [11, 12],
    [0, 13], [13, 14], [14, 15], [15, 16],
    [0, 17], [17, 18], [18, 19], [19, 20],
    [5, 9], [9, 13], [13, 17],
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final shoulderLeft = frame.body['BnOmbro_L'];
    final shoulderRight = frame.body['BnOmbro_R'];
    final elbowLeft = frame.body['BnAntBraco_L'];
    final elbowRight = frame.body['BnAntBraco_R'];
    final wristLeft = frame.body['BnMao_L'];
    final wristRight = frame.body['BnMao_R'];
    if (shoulderLeft == null ||
        shoulderRight == null ||
        elbowLeft == null ||
        elbowRight == null ||
        wristLeft == null ||
        wristRight == null) {
      return;
    }

    Offset direction(ReferencePoint start, ReferencePoint end) {
      final delta = Offset(end.x - start.x, start.y - end.y);
      return delta.distance < 0.0001
          ? const Offset(0, 1)
          : delta / delta.distance;
    }

    // Unity's avatar uses bone lengths that are unsuitable for a flat
    // landmark view. Preserve each joint's direction while reconstructing a
    // stable, human-proportioned upper body.
    const modelShoulderLeft = Offset(-1, 0);
    const modelShoulderRight = Offset(1, 0);
    final modelElbowLeft =
        modelShoulderLeft + direction(shoulderLeft, elbowLeft) * 1.25;
    final modelElbowRight =
        modelShoulderRight + direction(shoulderRight, elbowRight) * 1.25;
    final modelWristLeft =
        modelElbowLeft + direction(elbowLeft, wristLeft) * 1.15;
    final modelWristRight =
        modelElbowRight + direction(elbowRight, wristRight) * 1.15;

    final scale = math.min(size.width / 6.2, size.height / 5.2);
    final center = Offset(size.width / 2, size.height * 0.4);
    Offset projectModel(Offset point) => center + point * scale;

    List<Offset> normalizeHand(
      List<ReferencePoint> hand,
      ReferencePoint rawWrist,
      Offset modelWrist,
    ) {
      final relative = hand
          .map(
            (point) => Offset(
              point.x - rawWrist.x,
              rawWrist.y - point.y,
            ),
          )
          .toList(growable: false);
      final radius = relative.fold<double>(
        0,
        (largest, point) => math.max(largest, point.distance),
      );
      final handScale = 0.58 / math.max(radius, 0.001);
      return relative
          .map((point) => modelWrist + point * handScale)
          .toList(growable: false);
    }

    final modelLeftHand = normalizeHand(
      frame.leftHand,
      wristLeft,
      modelWristLeft,
    );
    final modelRightHand = normalizeHand(
      frame.rightHand,
      wristRight,
      modelWristRight,
    );

    final linePaint = Paint()
      ..color = color
      ..strokeWidth = math.max(3, scale * 0.07)
      ..strokeCap = StrokeCap.round;
    final jointPaint = Paint()..color = Colors.white;
    final torsoPaint = Paint()
      ..color = color.withValues(alpha: 0.14)
      ..style = PaintingStyle.fill;
    final outlinePaint = Paint()
      ..color = color.withValues(alpha: 0.65)
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(2, scale * 0.035);

    final torso = Path()
      ..moveTo(
        projectModel(modelShoulderLeft).dx,
        projectModel(modelShoulderLeft).dy,
      )
      ..lineTo(
        projectModel(modelShoulderRight).dx,
        projectModel(modelShoulderRight).dy,
      )
      ..lineTo(projectModel(const Offset(0.72, 2.05)).dx,
          projectModel(const Offset(0.72, 2.05)).dy)
      ..lineTo(projectModel(const Offset(-0.72, 2.05)).dx,
          projectModel(const Offset(-0.72, 2.05)).dy)
      ..close();
    canvas.drawPath(torso, torsoPaint);
    canvas.drawPath(torso, outlinePaint);

    canvas.drawLine(
      projectModel(modelShoulderLeft),
      projectModel(modelShoulderRight),
      linePaint,
    );
    canvas.drawLine(
      projectModel(modelShoulderLeft),
      projectModel(modelElbowLeft),
      linePaint,
    );
    canvas.drawLine(
      projectModel(modelElbowLeft),
      projectModel(modelWristLeft),
      linePaint,
    );
    canvas.drawLine(
      projectModel(modelShoulderRight),
      projectModel(modelElbowRight),
      linePaint,
    );
    canvas.drawLine(
      projectModel(modelElbowRight),
      projectModel(modelWristRight),
      linePaint,
    );
    canvas.drawLine(
      projectModel(const Offset(0, -0.42)),
      projectModel(const Offset(0, 0.16)),
      outlinePaint,
    );
    canvas.drawCircle(
      projectModel(const Offset(0, -0.92)),
      scale * 0.48,
      torsoPaint,
    );
    canvas.drawCircle(
      projectModel(const Offset(0, -0.92)),
      scale * 0.48,
      outlinePaint,
    );

    void drawHand(List<Offset> hand) {
      for (final connection in _handConnections) {
        canvas.drawLine(
          projectModel(hand[connection[0]]),
          projectModel(hand[connection[1]]),
          linePaint,
        );
      }
      for (final joint in hand) {
        canvas.drawCircle(
          projectModel(joint),
          math.max(2.2, scale * 0.035),
          jointPaint,
        );
      }
    }

    drawHand(modelLeftHand);
    drawHand(modelRightHand);
  }

  @override
  bool shouldRepaint(covariant _MotionPainter oldDelegate) {
    return oldDelegate.frame != frame || oldDelegate.color != color;
  }
}
