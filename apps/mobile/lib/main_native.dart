import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:hand_landmarker/hand_landmarker.dart';

import 'data/native_training_model.dart';
import 'domain/interfaces/sign_interpreter.dart';
import 'domain/sign_phrase_composer.dart';
import 'domain/recognition_policy.dart';
import 'presentation/screens/conversation_screen.dart';
import 'presentation/screens/home_screen.dart';
import 'presentation/screens/trainer_screen.dart';

late final List<CameraDescription> _availableCameras;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  _availableCameras = await availableCameras();
  runApp(
    const ProviderScope(
      child: LibraiNativeApp(),
    ),
  );
}

class LibraiNativeApp extends StatelessWidget {
  const LibraiNativeApp({super.key});

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const HomeScreen(),
        ),
        GoRoute(
          path: '/translate',
          builder: (context, state) => const NativeTranslationScreen(),
        ),
        GoRoute(
          path: '/conversation',
          builder: (context, state) => const ConversationScreen(),
        ),
        GoRoute(
          path: '/trainer',
          builder: (context, state) => const TrainerScreen(),
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
  final NativeModelRepository _modelRepository = NativeModelRepository();
  final LocalKnnInterpreter _interpreter = LocalKnnInterpreter();
  final SignPhraseComposer _phraseComposer = SignPhraseComposer();
  final Stopwatch _inferenceWatch = Stopwatch();
  final List<String> _predictionHistory = [];

  CameraController? _camera;
  HandLandmarkerPlugin? _landmarker;
  StreamSubscription<List<Hand>>? _landmarkSubscription;

  List<Hand> _hands = const [];
  NativeTrainingModel? _model;
  bool _initialized = false;
  bool _processingFrame = false;
  bool _paused = false;
  String? _error;
  String _detectedText = 'Sinalize em frente à câmera';
  double _confidence = 0;
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
      final modelFuture = _modelRepository.synchronize();
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
      _camera = camera;
      _landmarker = landmarker;
      _landmarkSubscription =
          landmarker.landmarkStream.listen(_handleLandmarks);
      await camera.startImageStream(_processCameraFrame);

      final model = await modelFuture;
      _interpreter.load(model);
      if (!mounted) return;
      setState(() {
        _model = model;
        _initialized = true;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = 'Falha ao iniciar o modo nativo: $error');
    }
  }

  void _processCameraFrame(CameraImage image) {
    final camera = _camera;
    final landmarker = _landmarker;
    if (_paused ||
        !_initialized ||
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
      _framesPerSecond =
          _resultsInWindow * 1000 / elapsedWindow.inMilliseconds;
      _resultsInWindow = 0;
      _fpsWindowStarted = now;
    }

    PredictionResult? bestPrediction;
    for (final hand in hands) {
      final points = hand.landmarks
          .map(
            (point) => <String, double>{
              'x': point.x,
              'y': point.y,
              'z': point.z,
            },
          )
          .toList(growable: false);
      final prediction = _interpreter.predict(points);
      if (bestPrediction == null ||
          prediction.confidence > bestPrediction.confidence) {
        bestPrediction = prediction;
      }
    }

    final validPrediction = bestPrediction != null &&
        bestPrediction.label != 'SINAL_DESCONHECIDO' &&
        bestPrediction.label != 'DADOS_INSUFICIENTES' &&
        bestPrediction.confidence >= 0.70;

    if (validPrediction) {
      if (RecognitionPolicy.isUnsupportedStaticAlphabetPrediction(
        bestPrediction.label,
      )) {
        _predictionHistory.clear();
        _detectedText =
            'Sinal com movimento ainda não confirmado pelo modelo temporal';
        _confidence = 0;
        if (!mounted) return;
        setState(() {
          _hands = hands;
          _latencyMilliseconds = _inferenceWatch.elapsedMilliseconds;
        });
        return;
      }
      _predictionHistory.add(bestPrediction.label);
      if (_predictionHistory.length > 2) _predictionHistory.removeAt(0);
      if (_predictionHistory.length == 2 &&
          _predictionHistory[0] == _predictionHistory[1]) {
        final composition = _phraseComposer.accept(bestPrediction.label);
        if (composition != null) {
          _detectedText = composition.text;
          _confidence = bestPrediction.confidence;
        }
      }
    } else {
      _predictionHistory.clear();
      if (hands.isEmpty) {
        _phraseComposer.releaseCurrentSign();
        _detectedText = 'Sinalize em frente à câmera';
        _confidence = 0;
      }
    }

    if (!mounted) return;
    setState(() {
      _hands = hands;
      _latencyMilliseconds = _inferenceWatch.elapsedMilliseconds;
    });
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
    _phraseComposer.reset();
    _camera?.stopImageStream();
    _camera?.dispose();
    _landmarker?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(_error!, textAlign: TextAlign.center),
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
              Text('Preparando câmera e modelo nativos…'),
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
                          'Librai • Nativo',
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      _statusChip(
                        _model?.isReady == true
                            ? 'Modelo ${_model!.version}'
                            : 'Sem modelo',
                        _model?.isReady == true ? Colors.green : Colors.red,
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
                      _statusChip('Inferência local', Colors.purple),
                    ],
                  ),
                  const Spacer(),
                  Semantics(
                    liveRegion: true,
                    label: 'Tradução detectada: $_detectedText',
                    child: Text(
                      _detectedText,
                      style: const TextStyle(
                        fontSize: 34,
                        height: 1.05,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _confidence > 0
                        ? 'Confiança ${(_confidence * 100).round()}%'
                        : 'Aguardando sinalização',
                    style: const TextStyle(fontSize: 16),
                  ),
                  const SizedBox(height: 18),
                  Center(
                    child: IconButton.filled(
                      tooltip: _paused ? 'Retomar tradução' : 'Pausar tradução',
                      onPressed: () => setState(() => _paused = !_paused),
                      iconSize: 32,
                      constraints: const BoxConstraints.tightFor(
                        width: 64,
                        height: 64,
                      ),
                      icon: Icon(_paused ? Icons.play_arrow : Icons.pause),
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
    [0, 1], [1, 2], [2, 3], [3, 4],
    [0, 5], [5, 6], [6, 7], [7, 8],
    [5, 9], [9, 10], [10, 11], [11, 12],
    [9, 13], [13, 14], [14, 15], [15, 16],
    [13, 17], [0, 17], [17, 18], [18, 19], [19, 20],
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
