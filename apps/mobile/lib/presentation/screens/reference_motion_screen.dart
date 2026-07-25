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
    final allPoints = [
      ...frame.body.values,
      ...frame.leftHand,
      ...frame.rightHand,
    ];
    if (allPoints.isEmpty) return;
    final minX = allPoints.map((point) => point.x).reduce(math.min);
    final maxX = allPoints.map((point) => point.x).reduce(math.max);
    final minY = allPoints.map((point) => point.y).reduce(math.min);
    final maxY = allPoints.map((point) => point.y).reduce(math.max);
    final width = math.max(0.001, maxX - minX);
    final height = math.max(0.001, maxY - minY);
    final scale = math.min(size.width * 0.84 / width, size.height * 0.84 / height);

    Offset project(ReferencePoint point) => Offset(
          size.width / 2 + (point.x - (minX + maxX) / 2) * scale,
          size.height / 2 - (point.y - (minY + maxY) / 2) * scale,
        );

    final linePaint = Paint()
      ..color = color
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final jointPaint = Paint()..color = Colors.white;

    void bodyLine(String start, String end) {
      final first = frame.body[start];
      final second = frame.body[end];
      if (first != null && second != null) {
        canvas.drawLine(project(first), project(second), linePaint);
      }
    }

    bodyLine('BnOmbro_L', 'BnOmbro_R');
    bodyLine('BnOmbro_L', 'BnAntBraco_L');
    bodyLine('BnAntBraco_L', 'BnMao_L');
    bodyLine('BnOmbro_R', 'BnAntBraco_R');
    bodyLine('BnAntBraco_R', 'BnMao_R');

    final head = frame.body['BnCabeca'];
    if (head != null) {
      canvas.drawCircle(project(head), 12, linePaint);
    }

    void drawHand(List<ReferencePoint> hand) {
      for (final connection in _handConnections) {
        canvas.drawLine(
          project(hand[connection[0]]),
          project(hand[connection[1]]),
          linePaint,
        );
      }
      for (final joint in hand) {
        canvas.drawCircle(project(joint), 2.8, jointPaint);
      }
    }

    drawHand(frame.leftHand);
    drawHand(frame.rightHand);
  }

  @override
  bool shouldRepaint(covariant _MotionPainter oldDelegate) {
    return oldDelegate.frame != frame || oldDelegate.color != color;
  }
}
