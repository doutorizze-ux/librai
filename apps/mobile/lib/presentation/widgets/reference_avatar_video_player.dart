import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

class ReferenceAvatarVideoPlayer extends StatefulWidget {
  const ReferenceAvatarVideoPlayer({
    required this.assetPath,
    required this.label,
    required this.fallback,
    this.compact = false,
    this.loop = true,
    this.onCompleted,
    super.key,
  });

  final String assetPath;
  final String label;
  final Widget fallback;
  final bool compact;
  final bool loop;
  final VoidCallback? onCompleted;

  @override
  State<ReferenceAvatarVideoPlayer> createState() =>
      _ReferenceAvatarVideoPlayerState();
}

class _ReferenceAvatarVideoPlayerState
    extends State<ReferenceAvatarVideoPlayer> {
  VideoPlayerController? _controller;
  Object? _loadError;
  bool _completionReported = false;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  @override
  void didUpdateWidget(covariant ReferenceAvatarVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.assetPath != widget.assetPath) {
      _disposeController();
      _loadError = null;
      _completionReported = false;
      _initialize();
    }
  }

  Future<void> _initialize() async {
    final controller = VideoPlayerController.asset(widget.assetPath);
    _controller = controller;
    try {
      await controller.initialize();
      await controller.setLooping(widget.loop);
      await controller.setVolume(0);
      controller.addListener(_handlePlayback);
      if (!mounted || controller != _controller) return;
      setState(() {});
      await controller.play();
    } catch (error) {
      if (!mounted || controller != _controller) return;
      setState(() => _loadError = error);
    }
  }

  void _handlePlayback() {
    final controller = _controller;
    if (controller == null || widget.loop || _completionReported) return;
    final value = controller.value;
    if (!value.isInitialized || value.duration == Duration.zero) return;
    if (value.position >= value.duration - const Duration(milliseconds: 60)) {
      _completionReported = true;
      widget.onCompleted?.call();
    }
    if (mounted) setState(() {});
  }

  void _disposeController() {
    final controller = _controller;
    _controller = null;
    controller?.removeListener(_handlePlayback);
    controller?.dispose();
  }

  @override
  void dispose() {
    _disposeController();
    super.dispose();
  }

  Future<void> _togglePlayback() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    if (controller.value.isPlaying) {
      await controller.pause();
    } else {
      if (controller.value.position >= controller.value.duration) {
        _completionReported = false;
        await controller.seekTo(Duration.zero);
      }
      await controller.play();
    }
    if (mounted) setState(() {});
  }

  Future<void> _replay() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;
    _completionReported = false;
    await controller.seekTo(Duration.zero);
    await controller.play();
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    if (_loadError != null) return widget.fallback;

    final controller = _controller;
    final media = controller == null || !controller.value.isInitialized
        ? const Center(
            child: CircularProgressIndicator(
              semanticsLabel: 'Carregando avatar realista',
            ),
          )
        : _videoSurface(controller);

    return Column(
      children: [
        if (widget.compact)
          AspectRatio(aspectRatio: 0.9, child: media)
        else
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: media,
            ),
          ),
        if (!widget.compact && controller?.value.isInitialized == true)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _togglePlayback,
                    icon: Icon(
                      controller!.value.isPlaying
                          ? Icons.pause
                          : Icons.play_arrow,
                    ),
                    label: Text(
                      controller.value.isPlaying ? 'Pausar' : 'Reproduzir',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                IconButton.filledTonal(
                  tooltip: 'Repetir desde o início',
                  onPressed: _replay,
                  icon: const Icon(Icons.replay),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _videoSurface(VideoPlayerController controller) {
    final size = controller.value.size;
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: ColoredBox(
        color: const Color(0xFF77777D),
        child: Semantics(
          image: true,
          label:
              'Avatar realista demonstrando o sinal ${widget.label.replaceAll('_', ' ')}',
          child: SizedBox.expand(
            child: FittedBox(
              fit: BoxFit.cover,
              clipBehavior: Clip.hardEdge,
              child: SizedBox(
                width: size.width,
                height: size.height,
                child: VideoPlayer(controller),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
