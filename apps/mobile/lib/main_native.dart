import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:hand_landmarker/hand_landmarker.dart';

import 'domain/sign_phrase_composer.dart';
import 'platform/mock_interpreter.dart';
import 'platform/tts_service.dart';
import 'presentation/screens/home_screen.dart';
import 'presentation/screens/libras_access_screen.dart';
import 'presentation/screens/trainer_screen.dart';

late final List<CameraDescription> _availableCameras;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  _availableCameras = await availableCameras();
  runApp(const ProviderScope(child: LibraiNativeApp()));
}

class LibraiNativeApp extends StatelessWidget {
  const LibraiNativeApp({super.key});

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
        GoRoute(
          path: '/translate',
          builder: (context, state) => const NativeTranslationScreen(),
        ),
        GoRoute(
          path: '/trainer',
          builder: (context, state) => const TrainerScreen(),
        ),
        GoRoute(
          path: '/libras',
          builder: (context, state) => const LibrasAccessScreen(),
        ),
      ],
    );

    return MaterialApp.router(
      title: 'Librai',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF705A9E),
          brightness: Brightness.dark,
        ),
      ),
      routerConfig: router,
    );
  }
}

class NativeTranslationScreen extends StatefulWidget {
  const NativeTranslationScreen({super.key});

  @override
  State<NativeTranslationScreen> createState() =>
      _NativeTranslationScreenState();
}

class _NativeTranslationScreenState extends State<NativeTranslationScreen>
    with WidgetsBindingObserver {
  final MockSignInterpreter _interpreter = MockSignInterpreter();
  final SignPhraseComposer _phraseComposer = SignPhraseComposer();
  final TtsService _ttsService = TtsService();
  final Stopwatch _inferenceWatch = Stopwatch();
  final List<String> _predictionHistory = [];

  CameraController? _camera;
  HandLandmarkerPlugin? _landmarker;
  StreamSubscription<List<Hand>>? _landmarkSubscription;

  List<Hand> _hands = const [];
  bool _initialized = false;
  bool _processingFrame = false;
  bool _capturing = true;
  bool _submitting = false;
  String? _fatalError;
  String? _error;
  String? _selectedLabel;
  String? _translatedText;
  double _framesPerSecond = 0;
  int _latencyMilliseconds = 0;
  int _resultsInWindow = 0;
  DateTime _fpsWindowStarted = DateTime.now();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      final frontCamera = _availableCameras.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.front,
        orElse: () => _availableCameras.first,
      );

      final camera = CameraController(
        frontCamera,
        ResolutionPreset.high,
        enableAudio: false,
      );
      final landmarker = HandLandmarkerPlugin.create(
        numHands: 2,
        minHandDetectionConfidence: 0.5,
        delegate: HandLandmarkerDelegate.gpu,
      );

      await camera.initialize();
      await _interpreter.loadModel('trained-sequence-v2');
      _camera = camera;
      _landmarker = landmarker;
      _landmarkSubscription = landmarker.landmarkStream.listen(
        _handleLandmarks,
      );
      await camera.startImageStream(_processCameraFrame);

      if (!mounted) return;
      setState(() => _initialized = true);
    } catch (error) {
      if (!mounted) return;
      setState(() => _fatalError = 'Falha ao iniciar o modo nativo: $error');
    }
  }

  void _processCameraFrame(CameraImage image) {
    final camera = _camera;
    final landmarker = _landmarker;
    if (!_initialized ||
        _processingFrame ||
        camera == null ||
        landmarker == null) {
      return;
    }

    _processingFrame = true;
    _inferenceWatch
      ..reset()
      ..start();
    try {
      landmarker.processFrame(image, camera.description.sensorOrientation);
    } catch (error) {
      _processingFrame = false;
      _inferenceWatch.stop();
      debugPrint('Falha ao enviar quadro ao MediaPipe: $error');
    }
  }

  void _handleLandmarks(List<Hand> hands) {
    _inferenceWatch.stop();
    _processingFrame = false;
    _resultsInWindow++;

    final now = DateTime.now();
    final elapsedWindow = now.difference(_fpsWindowStarted);
    if (elapsedWindow.inMilliseconds >= 1000) {
      _framesPerSecond = _resultsInWindow * 1000 / elapsedWindow.inMilliseconds;
      _resultsInWindow = 0;
      _fpsWindowStarted = now;
    }

    if (hands.isNotEmpty && _capturing) {
      final orderedHands = [...hands]
        ..sort((a, b) => a.landmarks.first.x.compareTo(b.landmarks.first.x));
      final frame = <String, dynamic>{
        'timestamp_ms': DateTime.now().millisecondsSinceEpoch,
        'hands': [
          for (var index = 0; index < orderedHands.length && index < 2; index++)
            {
              'handedness': index == 0 ? 'Left' : 'Right',
              'score': 1.0,
              'landmarks': orderedHands[index]
                  .landmarks
                  .map((point) => {'x': point.x, 'y': point.y, 'z': point.z})
                  .toList(growable: false),
            },
        ],
      };
      _interpreter.addHandFrame(frame);
      if (_interpreter.hasEnoughHandFrames && !_submitting) {
        unawaited(_recognizeBufferedSequence());
      }
    } else if (hands.isEmpty) {
      _predictionHistory.clear();
      _interpreter.resetSequence();
      _phraseComposer.releaseCurrentSign();
    }

    if (!mounted) return;
    setState(() {
      _hands = hands;
      _latencyMilliseconds = _inferenceWatch.elapsedMilliseconds;
    });
  }

  Future<void> _recognizeBufferedSequence() async {
    if (!_capturing || _submitting) return;
    _submitting = true;
    try {
      final prediction = await _interpreter.predictBufferedSequence();
      if (!mounted || !_capturing) return;
      if (prediction.label == 'SINAL_DESCONHECIDO' ||
          prediction.label == 'DADOS_INSUFICIENTES' ||
          prediction.confidence < 0.70) {
        return;
      }

      _predictionHistory.add(prediction.label);
      if (_predictionHistory.length > 2) {
        _predictionHistory.removeAt(0);
      }
      final consistent = prediction.confidence >= 0.86 ||
          (_predictionHistory.length == 2 &&
              _predictionHistory[0] == _predictionHistory[1]);
      if (!consistent) return;

      _interpreter.resetSequence();
      _predictionHistory.clear();
      final composition = _phraseComposer.accept(prediction.label);
      if (composition == null) return;
      setState(() {
        _selectedLabel = prediction.label;
        _translatedText = composition.text;
        _error = null;
      });
      if (composition.isFinal) {
        await _ttsService.speak(composition.text);
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error =
            'Não foi possível analisar agora. Verifique a conexão e tente novamente.';
      });
    } finally {
      _submitting = false;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      _camera?.stopImageStream();
    } else if (state == AppLifecycleState.resumed &&
        _camera?.value.isInitialized == true &&
        _camera?.value.isStreamingImages == false) {
      _camera?.startImageStream(_processCameraFrame);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _landmarkSubscription?.cancel();
    _predictionHistory.clear();
    _interpreter.resetSequence();
    _phraseComposer.reset();
    _camera?.stopImageStream();
    _camera?.dispose();
    _landmarker?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_fatalError != null) {
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(_fatalError!, textAlign: TextAlign.center),
          ),
        ),
      );
    }

    final camera = _camera;
    if (!_initialized || camera == null) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.all(Radius.circular(24)),
                child: Image(
                  image: AssetImage('assets/branding/librai-icon.png'),
                  width: 112,
                  height: 112,
                  fit: BoxFit.cover,
                ),
              ),
              SizedBox(height: 24),
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Preparando câmera nativa…'),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          _buildCameraPreview(camera),
          CustomPaint(painter: _HandPainter(_hands)),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0x99000000),
                  Colors.transparent,
                  Color(0xDD000000),
                ],
                stops: [0, 0.48, 1],
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      IconButton.filledTonal(
                        tooltip: 'Voltar ao início',
                        onPressed: () => context.go('/'),
                        icon: const Icon(Icons.arrow_back),
                      ),
                      const SizedBox(width: 8),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: Image.asset(
                          'assets/branding/librai-icon.png',
                          width: 42,
                          height: 42,
                          fit: BoxFit.cover,
                          semanticLabel: 'Logo do Librai',
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Expanded(
                        child: Text(
                          'Tradução ao vivo',
                          style: TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      _statusChip(
                        _capturing ? 'TRADUZINDO' : 'PAUSADO',
                        _capturing ? Colors.green : Colors.orange,
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _statusChip(
                        '${_hands.length} mão${_hands.length == 1 ? '' : 's'}',
                        _hands.isNotEmpty ? Colors.green : Colors.orange,
                      ),
                      _statusChip(
                        '${_latencyMilliseconds} ms',
                        _latencyMilliseconds <= 50
                            ? Colors.green
                            : Colors.orange,
                      ),
                      _statusChip(
                        '${_framesPerSecond.toStringAsFixed(1)} FPS',
                        Colors.blue,
                      ),
                    ],
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xE81B1820),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: Colors.white24),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          _instruction,
                          style: const TextStyle(
                            fontSize: 18,
                            height: 1.25,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 8),
                          Semantics(
                            liveRegion: true,
                            child: Text(
                              _error!,
                              style: const TextStyle(
                                color: Color(0xFFFFB4AB),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                        if (_translatedText != null) ...[
                          const SizedBox(height: 12),
                          Semantics(
                            liveRegion: true,
                            label: 'Tradução: $_translatedText',
                            child: Text(
                              _translatedText!,
                              style: const TextStyle(
                                color: Color(0xFFB9FFDA),
                                fontSize: 28,
                                height: 1.1,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: 8),
                        Semantics(
                          button: true,
                          label: _capturing
                              ? 'Pausar tradução automática'
                              : 'Retomar tradução automática',
                          child: FilledButton.icon(
                            style: FilledButton.styleFrom(
                              minimumSize: const Size(double.infinity, 58),
                              backgroundColor: const Color(0xFF7158A0),
                            ),
                            onPressed: () {
                              setState(() {
                                _capturing = !_capturing;
                                _error = null;
                              });
                              _interpreter.resetSequence();
                              _predictionHistory.clear();
                              _phraseComposer.releaseCurrentSign();
                            },
                            icon: Icon(
                              _capturing ? Icons.pause : Icons.play_arrow,
                            ),
                            label: Text(
                              _capturing
                                  ? 'Pausar tradução'
                                  : 'Retomar tradução',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  String get _instruction {
    if (!_capturing) return 'Tradução pausada.';
    if (_hands.isEmpty) return 'Mostre as mãos e sinalize normalmente.';
    if (_submitting) return 'Reconhecendo o movimento…';
    if (_selectedLabel != null) {
      return 'Sinal reconhecido: ${SignPhraseComposer.displayLabel(_selectedLabel!)}';
    }
    return 'Tradução automática ativa. Faça um sinal do começo ao fim.';
  }

  Widget _buildCameraPreview(CameraController camera) {
    final previewSize = camera.value.previewSize!;
    return ClipRect(
      child: FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(
          width: previewSize.height,
          height: previewSize.width,
          child: CameraPreview(camera),
        ),
      ),
    );
  }

  Widget _statusChip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}

class _HandPainter extends CustomPainter {
  const _HandPainter(this.hands);

  final List<Hand> hands;

  static const connections = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 4],
    [0, 5],
    [5, 6],
    [6, 7],
    [7, 8],
    [5, 9],
    [9, 10],
    [10, 11],
    [11, 12],
    [9, 13],
    [13, 14],
    [14, 15],
    [15, 16],
    [13, 17],
    [0, 17],
    [17, 18],
    [18, 19],
    [19, 20],
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final pointPaint = Paint()..color = Colors.white;
    final linePaint = Paint()
      ..color = const Color(0xFF00FFCC)
      ..strokeWidth = 3;

    for (final hand in hands) {
      for (final connection in connections) {
        final start = hand.landmarks[connection[0]];
        final end = hand.landmarks[connection[1]];
        canvas.drawLine(
          Offset((1 - start.x) * size.width, start.y * size.height),
          Offset((1 - end.x) * size.width, end.y * size.height),
          linePaint,
        );
      }
      for (final point in hand.landmarks) {
        canvas.drawCircle(
          Offset((1 - point.x) * size.width, point.y * size.height),
          4,
          pointPaint,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _HandPainter oldDelegate) =>
      oldDelegate.hands != hands;
}
