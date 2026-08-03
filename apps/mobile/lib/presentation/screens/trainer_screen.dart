import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import '../../platform/mediapipe_interop.dart';
import '../../platform/tts_service.dart';
import '../../platform/client_platform.dart';
import '../../domain/sign_phrase_composer.dart';
import '../../domain/lexical_sign_label.dart';
import '../../data/training_draft_store.dart';
import '../../data/trainer_session_store.dart';

class TrainerScreen extends StatefulWidget {
  const TrainerScreen({super.key});

  @override
  State<TrainerScreen> createState() => _TrainerScreenState();
}

class _TrainerScreenState extends State<TrainerScreen> {
  final MediaPipeService _visionService = MediaPipeService();
  final TtsService _ttsService = TtsService();
  final TrainerSessionStore _sessionStore = TrainerSessionStore();
  final TrainingDraftStore _draftStore = TrainingDraftStore();
  final Dio _dio = Dio(BaseOptions(
    baseUrl: const String.fromEnvironment('API_URL',
        defaultValue: 'https://api.tvcatolica.site'),
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 5),
  ));

  final TextEditingController _signNameController = TextEditingController();
  Timer? _frameTimer;
  Timer? _countdownTimer;

  bool _isRecording = false;
  int _countdown = 3;
  bool _isCountingDown = false;
  List<Map<String, double>> _recordedLandmarks = [];
  final List<Map<String, dynamic>> _recordedHandFrames = [];
  final List<Map<String, dynamic>> _recordedHolisticFrames = [];
  bool _handsDetected = false;
  bool _faceDetected = false;
  bool _bodyDetected = false;
  String _statusMessage = "Posicione a mão em frente à câmera";
  bool _isUploading = false;

  Timer? _debounceTimer;
  int _existingSamplesCount = 0;
  bool _isLoadingCount = false;
  List<Map<String, dynamic>> _trainedSignsSummary = [];
  bool _isLoadingSummary = false;
  List<Map<String, dynamic>> _mySamples = [];
  bool _isLoadingMySamples = false;
  final Set<String> _deletingSampleIds = {};
  String? _trainerToken;
  String? _trainerName;
  bool _trainerServicesStarted = false;
  int _validCapturedFrames = 0;
  int _lastCapturedRevision = -1;
  String _trackingQuality = 'waiting';
  int _handsCount = 0;
  double _inferenceFps = 0;
  int _inferenceLatencyMs = 0;
  int _handScreenRatio = 0;
  static const int _requiredRepetitions = 5;
  int _savedRepetitionsCount = 0;
  bool _isRestoringDraft = false;
  bool _hasPendingDraftUpload = false;
  String? _activeTrainingSign;

  bool get _holisticCaptureReady =>
      _trackingQuality == 'good' && _faceDetected && _bodyDetected;

  Options get _authorizedOptions => Options(
        headers: {'Authorization': 'Bearer $_trainerToken'},
      );

  @override
  void initState() {
    super.initState();
    // O PlatformView precisa existir antes do primeiro build. Se o registro
    // ocorrer somente após o diálogo de autenticação, o Safari mantém a
    // visualização criada sem factory como uma superfície preta.
    _visionService.setCaptureMode('holistic');
    _visionService.registerVideoView();
    _signNameController.addListener(_onSignNameChanged);
    WidgetsBinding.instance
        .addPostFrameCallback((_) => _restoreTrainerAccess());
  }

  Future<void> _restoreTrainerAccess() async {
    final session = await _sessionStore.restore();
    if (!mounted) return;
    if (session != null) {
      _trainerToken = session.token;
      _trainerName = session.trainerName;
      try {
        await _dio.get(
          '/v1/training/my-samples',
          queryParameters: const {'limit': 1},
          options: _authorizedOptions,
        );
        if (!mounted) return;
        _startTrainerServices();
        return;
      } on DioException catch (error) {
        if (error.response?.statusCode != 401) {
          if (!mounted) return;
          _startTrainerServices();
          return;
        }
        await _sessionStore.clear();
        _trainerToken = null;
        _trainerName = null;
      }
    }
    await _requestTrainerAccess();
  }

  Future<void> _requestTrainerAccess() async {
    final nameController = TextEditingController();
    final codeController = TextEditingController();
    String? errorMessage;

    final authenticated = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Acesso do professor'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Identifique-se antes de contribuir. Cada envio ficará '
                'registrado para controle de qualidade.',
              ),
              const SizedBox(height: 16),
              TextField(
                controller: nameController,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(
                  labelText: 'Nome completo',
                  prefixIcon: Icon(Icons.person_outline),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: codeController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Código de professor ou administrativo',
                  prefixIcon: Icon(Icons.lock_outline),
                ),
                onSubmitted: (_) {},
              ),
              if (errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () async {
                final name = nameController.text.trim();
                final code = codeController.text;
                if (name.length < 2 || code.length < 8) {
                  setDialogState(() {
                    errorMessage = 'Informe seu nome e o código recebido.';
                  });
                  return;
                }
                try {
                  final response = await _dio.post(
                    '/v1/training/auth',
                    data: {'trainer_name': name, 'access_code': code},
                  );
                  _trainerToken = response.data['access_token'] as String?;
                  _trainerName = name;
                  if (_trainerToken == null) throw StateError('Token ausente');
                  final expiresInSeconds =
                      (response.data['expires_in_seconds'] as num?)?.toInt() ??
                          604800;
                  await _sessionStore.save(
                    TrainerSession(
                      token: _trainerToken!,
                      trainerName: name,
                      expiresAt: DateTime.now().add(
                        Duration(seconds: expiresInSeconds),
                      ),
                    ),
                  );
                  if (dialogContext.mounted) {
                    Navigator.pop(dialogContext, true);
                  }
                } on DioException catch (error) {
                  setDialogState(() {
                    errorMessage =
                        error.response?.data?['detail']?.toString() ??
                            'Não foi possível autenticar.';
                  });
                }
              },
              child: const Text('Entrar'),
            ),
          ],
        ),
      ),
    );

    nameController.dispose();
    codeController.dispose();
    if (!mounted) return;
    if (authenticated != true) {
      setState(() {
        _statusMessage =
            'Entre como professor para começar ou use a seta para voltar.';
      });
      return;
    }
    _startTrainerServices();
  }

  void _startTrainerServices() {
    if (_trainerServicesStarted) return;
    _trainerServicesStarted = true;
    _visionService.setCaptureMode('holistic');
    _visionService.start();
    _fetchSummary();
    _fetchMySamples();
    unawaited(_restoreTrainingDraft());
    _frameTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) {
      if (!mounted) return;
      final handsOk = _visionService.isHandsDetected();
      final faceOk = _visionService.isFaceDetected();
      final bodyOk = _visionService.isBodyDetected();
      final trackingQuality = _visionService.getTrackingQuality();
      final handsCount = _visionService.getHandsCount();
      final inferenceFps = _visionService.getInferenceFps();
      final inferenceLatencyMs = _visionService.getInferenceLatencyMs();
      final handScreenRatio = _visionService.getHandScreenRatio();
      if (_handsDetected != handsOk ||
          _faceDetected != faceOk ||
          _bodyDetected != bodyOk ||
          _trackingQuality != trackingQuality ||
          _handsCount != handsCount ||
          (_inferenceFps - inferenceFps).abs() >= 0.5 ||
          _inferenceLatencyMs != inferenceLatencyMs ||
          _handScreenRatio != handScreenRatio) {
        setState(() {
          _handsDetected = handsOk;
          _faceDetected = faceOk;
          _bodyDetected = bodyOk;
          _trackingQuality = trackingQuality;
          _handsCount = handsCount;
          _inferenceFps = inferenceFps;
          _inferenceLatencyMs = inferenceLatencyMs;
          _handScreenRatio = handScreenRatio;
        });
      }
    });
    setState(() {
      _statusMessage = 'Professor: $_trainerName • Posicione a mão na câmera';
    });
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    _countdownTimer?.cancel();
    _signNameController.removeListener(_onSignNameChanged);
    _signNameController.dispose();
    _debounceTimer?.cancel();
    _visionService.stop();
    super.dispose();
  }

  void _onSignNameChanged() {
    if (_activeTrainingSign != null) return;
    if (_trainerToken == null) return;
    final text = LexicalSignLabel.normalize(_signNameController.text);
    if (text.isEmpty) {
      setState(() {
        _existingSamplesCount = 0;
        _isLoadingCount = false;
      });
      return;
    }

    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 500), () async {
      if (!mounted) return;
      setState(() {
        _isLoadingCount = true;
      });

      try {
        final response = await _dio.get(
          '/v1/training/samples/count',
          queryParameters: {'sign_name': text},
          options: _authorizedOptions,
        );
        if (mounted && response.statusCode == 200) {
          setState(() {
            _existingSamplesCount = response.data['count'] as int? ?? 0;
          });
        }
      } catch (e) {
        debugPrint("Erro ao buscar contagem de amostras: $e");
      } finally {
        if (mounted) {
          setState(() {
            _isLoadingCount = false;
          });
        }
      }
    });
  }

  // Iniciar fluxo de gravação com contagem regressiva
  Future<void> _startRecordingFlow() async {
    if (_trainerToken == null) {
      await _requestTrainerAccess();
      if (_trainerToken == null) return;
    }
    if (_hasPendingDraftUpload) {
      final pending = await _draftStore.restore(_trainerName ?? '');
      if (pending != null) {
        await _uploadPendingRepetition(pending, isRecovery: true);
        return;
      }
      if (mounted) {
        setState(() => _hasPendingDraftUpload = false);
      }
    }
    final signName = LexicalSignLabel.normalize(_signNameController.text);
    if (signName.isEmpty) {
      _showSnackBar(
          "Por favor, digite o nome do sinal (ex: OBRIGADO)", Colors.redAccent);
      return;
    }

    if (!LexicalSignLabel.isValid(signName)) {
      _showSnackBar(
        "Digite o significado de uma única unidade de Libras. Ela pode ter "
        "mais de uma palavra, como TUDO BEM?.",
        Colors.orange,
      );
      return;
    }

    if (_activeTrainingSign != null && _activeTrainingSign != signName) {
      _showSnackBar(
        "Conclua as 5 repetições de $_activeTrainingSign antes de trocar o sinal.",
        Colors.orange,
      );
      return;
    }

    _activeTrainingSign ??= signName;

    setState(() {
      _isCountingDown = true;
      _countdown = 3;
      _statusMessage = "Prepare-se...";
    });

    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return;
      setState(() {
        if (_countdown > 1) {
          _countdown--;
        } else {
          timer.cancel();
          _isCountingDown = false;
          _startCapture(signName);
        }
      });
    });
  }

  // Captura por pelo menos 2 segundos. Em aparelhos mais lentos, estende até
  // 4 segundos para atingir 24 quadros realmente novos sem penalizar o professor.
  void _startCapture(String signName) {
    setState(() {
      _isRecording = true;
      _recordedLandmarks.clear();
      _recordedHandFrames.clear();
      _recordedHolisticFrames.clear();
      _validCapturedFrames = 0;
      _lastCapturedRevision = _visionService.getLandmarkRevision();
      _statusMessage = "Gravando sinal: $signName";
    });

    const minimumCaptureTicks = 60;
    const maximumCaptureTicks = 180;
    int frameCount = 0;
    Timer.periodic(const Duration(milliseconds: 33), (timer) async {
      if (!mounted || !_isRecording) {
        timer.cancel();
        return;
      }

      final revision = _visionService.getLandmarkRevision();
      if (revision == _lastCapturedRevision) {
        frameCount++;
        if (frameCount >= maximumCaptureTicks ||
            (frameCount >= minimumCaptureTicks && _validCapturedFrames >= 24)) {
          timer.cancel();
          _stopAndUploadCapture(signName);
        } else if (frameCount == minimumCaptureTicks && mounted) {
          setState(() {
            _statusMessage =
                'Continue o sinal: completando os quadros da repetição...';
          });
        }
        return;
      }
      _lastCapturedRevision = revision;
      final latest = _visionService.getLatestLandmarks();
      final handFrame = _visionService.getLatestHandFrame();
      final holisticFrame = _visionService.getLatestHolisticFrame();
      if (latest != null &&
          latest.length >= 21 &&
          latest.length % 21 == 0 &&
          _visionService.getTrackingQuality() == 'good' &&
          _visionService.isFaceDetected() &&
          _visionService.isBodyDetected()) {
        if (holisticFrame != null) {
          _recordedHolisticFrames.add(holisticFrame);
          _validCapturedFrames++;
        } else if (handFrame != null) {
          _recordedHandFrames.add(handFrame);
        } else {
          _recordedLandmarks.addAll(latest);
        }
      }

      frameCount++;
      if (frameCount >= maximumCaptureTicks ||
          (frameCount >= minimumCaptureTicks && _validCapturedFrames >= 24)) {
        timer.cancel();
        _stopAndUploadCapture(signName);
      } else if (frameCount == minimumCaptureTicks && mounted) {
        setState(() {
          _statusMessage =
              'Continue o sinal: completando os quadros da repetição...';
        });
      }
    });
  }

  // Finaliza a gravação e envia para a API do Coolify
  Future<void> _stopAndUploadCapture(String signName) async {
    setState(() {
      _isRecording = false;
      _statusMessage = "Validando repetição...";
    });

    if (_validCapturedFrames < 24) {
      setState(() {
        _statusMessage =
            "Captura insuficiente: mantenha mãos, rosto e tronco visíveis.";
      });
      _showSnackBar(
        "Gravação recusada: somente $_validCapturedFrames quadro(s) útil(eis). "
        "São necessários pelo menos 24.",
        Colors.redAccent,
      );
      return;
    }

    if (_recordedHolisticFrames.length < 24) {
      setState(() {
        _statusMessage =
            "Captura recusada: mantenha mãos, rosto e tronco visíveis.";
      });
      _showSnackBar(
        "A IA não recebeu a sequência completa de mãos, rosto e tronco. "
        "Reposicione-se e tente novamente.",
        Colors.redAccent,
      );
      return;
    }

    setState(() {
      _isUploading = true;
      _statusMessage = "Salvando esta repetição...";
    });

    final pending = PendingTrainingRepetition(
      captureId: _newCaptureId(),
      trainerName: _trainerName!,
      signName: signName,
      platform: currentClientPlatform(),
      cameraFacing: 'front',
      frames: _recordedHolisticFrames
          .map((frame) => Map<String, dynamic>.from(frame))
          .toList(growable: false),
      formatVersion: 4,
    );
    try {
      // A cópia local é criada antes da rede. Ela só é apagada depois que
      // o PostgreSQL confirmar o mesmo capture_id.
      await _draftStore.save(pending);
      if (!mounted) return;
      setState(() => _hasPendingDraftUpload = true);
      await _uploadPendingRepetition(pending);
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }
  }

  String _newCaptureId() {
    final random = Random.secure();
    return '${DateTime.now().microsecondsSinceEpoch}_'
        '${random.nextInt(0x7fffffff)}_${random.nextInt(0x7fffffff)}';
  }

  Future<void> _restoreTrainingDraft() async {
    if (_isRestoringDraft || _trainerToken == null || _trainerName == null) {
      return;
    }
    _isRestoringDraft = true;
    try {
      final pending = await _draftStore.restore(_trainerName!);
      if (pending != null) {
        if (mounted) {
          setState(() => _hasPendingDraftUpload = true);
        }
        await _uploadPendingRepetition(pending, isRecovery: true);
      }

      final response = await _dio.get(
        '/v1/training/drafts/current',
        options: _authorizedOptions,
      );
      if (!mounted || response.statusCode != 200) return;
      final active = response.data['active'] == true;
      final signName = response.data['sign_name']?.toString();
      final saved = (response.data['repetitions_saved'] as num?)?.toInt() ?? 0;
      setState(() {
        _activeTrainingSign = active ? signName : null;
        _savedRepetitionsCount = active ? saved : 0;
        if (active && signName != null) {
          _signNameController.text = signName;
          _statusMessage = 'Sessão recuperada: $saved/$_requiredRepetitions '
              'repetições de ${SignPhraseComposer.displayLabel(signName)}.';
        }
      });
    } on DioException catch (error) {
      debugPrint('Erro ao recuperar rascunho de treinamento: $error');
    } finally {
      _isRestoringDraft = false;
    }
  }

  Future<void> _uploadPendingRepetition(
    PendingTrainingRepetition pending, {
    bool isRecovery = false,
  }) async {
    if (_trainerToken == null) return;
    if (mounted) {
      setState(() {
        _isUploading = true;
        _statusMessage = isRecovery
            ? 'Recuperando a repetição interrompida...'
            : 'Salvando esta repetição no servidor...';
      });
    }
    try {
      final isHolistic = pending.formatVersion == 4;
      final response = await _dio.post(
        isHolistic
            ? '/v1/training/drafts-v4/repetitions'
            : '/v1/training/drafts/repetitions',
        options: Options(
          headers: {'Authorization': 'Bearer $_trainerToken'},
          receiveTimeout: const Duration(seconds: 20),
          sendTimeout: const Duration(seconds: 20),
        ),
        data: {
          'capture_id': pending.captureId,
          'sign_name': pending.signName,
          'format_version': pending.formatVersion,
          'capture_context': {
            'platform': pending.platform,
            'camera_facing': pending.cameraFacing,
          },
          if (isHolistic)
            'linguistic_metadata': {
              'regional_variation': pending.regionalVariation,
              'dominant_hand': pending.dominantHand,
            },
          'frames': pending.frames,
        },
      );
      if (response.statusCode != 201 || !mounted) return;

      await _draftStore.clear();
      final saved = (response.data['repetitions_saved'] as num?)?.toInt() ?? 0;
      final completed = response.data['completed'] == true;
      _recordedHandFrames.clear();
      _recordedHolisticFrames.clear();
      _recordedLandmarks.clear();
      setState(() {
        _hasPendingDraftUpload = false;
        if (completed) {
          _statusMessage =
              "Sinal '${SignPhraseComposer.displayLabel(pending.signName)}' "
              '${isHolistic ? 'coletado e aguardando validação da nova IA.' : 'concluído e salvo no servidor.'}';
          if (!isHolistic) {
            _existingSamplesCount += _requiredRepetitions;
          }
          _savedRepetitionsCount = 0;
          _activeTrainingSign = null;
        } else {
          _activeTrainingSign = pending.signName;
          _savedRepetitionsCount = saved;
          _statusMessage = 'Repetição $saved/$_requiredRepetitions salva no '
              'servidor. Repita ${SignPhraseComposer.displayLabel(pending.signName)}.';
        }
      });
      if (completed) {
        _ttsService.speak('Cinco repetições concluídas. Sinal gravado!');
        _showSnackBar(
          'Sinal concluído: as 5 repetições estão no servidor.',
          Colors.green,
        );
        _fetchSummary();
        _fetchMySamples();
      } else {
        _ttsService.speak(
          'Repetição $saved de $_requiredRepetitions concluída.',
        );
        _showSnackBar(
          'Repetição $saved/$_requiredRepetitions salva no servidor.',
          Colors.green,
        );
      }
    } on DioException catch (error) {
      debugPrint('Erro ao salvar repetição de treino: $error');
      if (!mounted) return;
      final sessionExpired = error.response?.statusCode == 401;
      final rejected = error.response != null &&
          error.response!.statusCode != null &&
          error.response!.statusCode! >= 400 &&
          error.response!.statusCode! < 500 &&
          !sessionExpired;
      final detail = error.response?.data?['detail']?.toString();
      if (rejected) {
        await _draftStore.clear();
        _recordedHandFrames.clear();
        _recordedLandmarks.clear();
      }
      if (!mounted) return;
      setState(() {
        _hasPendingDraftUpload = !rejected;
        _activeTrainingSign = pending.signName;
        _statusMessage = rejected
            ? detail ?? 'A repetição foi recusada. Grave novamente.'
            : sessionExpired
                ? 'Sua sessão expirou. A repetição está protegida neste aparelho; '
                    'entre novamente para enviá-la.'
                : detail ??
                    'Sem confirmação do servidor. A repetição continua salva '
                        'neste aparelho; toque no botão para tentar novamente.';
      });
      _showSnackBar(_statusMessage, Colors.redAccent);
      if (sessionExpired) {
        await _sessionStore.clear();
        _trainerToken = null;
        _trainerName = null;
        if (mounted) await _requestTrainerAccess();
      }
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }
  }

  Future<void> _fetchSummary() async {
    setState(() => _isLoadingSummary = true);
    try {
      final response = await _dio.get(
        '/v1/training/samples/summary',
        options: _authorizedOptions,
      );
      if (mounted && response.statusCode == 200) {
        final data = response.data as List<dynamic>? ?? [];
        final List<Map<String, dynamic>> summaryList = [];
        for (final item in data) {
          if (item is Map) {
            summaryList.add({
              'sign_name': item['sign_name']?.toString() ?? '',
              'count': (item['count'] as num?)?.toInt() ?? 0,
            });
          }
        }
        setState(() {
          _trainedSignsSummary = summaryList;
        });
      }
    } catch (e) {
      debugPrint("Erro ao buscar resumo de sinais: $e");
    } finally {
      if (mounted) setState(() => _isLoadingSummary = false);
    }
  }

  Future<void> _fetchMySamples() async {
    if (_trainerToken == null || _isLoadingMySamples) return;
    setState(() => _isLoadingMySamples = true);
    try {
      final response = await _dio.get(
        '/v1/training/my-samples',
        queryParameters: const {'limit': 50},
        options: _authorizedOptions,
      );
      if (!mounted || response.statusCode != 200) return;
      final data = response.data as List<dynamic>? ?? [];
      setState(() {
        _mySamples = data
            .whereType<Map>()
            .map(
              (item) => <String, dynamic>{
                'id': item['id']?.toString() ?? '',
                'sign_name': item['sign_name']?.toString() ?? '',
                'frame_count': (item['frame_count'] as num?)?.toInt() ?? 0,
                'created_at': item['created_at']?.toString() ?? '',
              },
            )
            .where((item) => (item['id'] as String).isNotEmpty)
            .toList(growable: false);
      });
    } catch (error) {
      debugPrint('Erro ao buscar sessões do professor: $error');
    } finally {
      if (mounted) setState(() => _isLoadingMySamples = false);
    }
  }

  Future<void> _confirmDeleteMySample(Map<String, dynamic> sample) async {
    final id = sample['id'] as String;
    final signName = sample['sign_name'] as String;
    final displayName = SignPhraseComposer.displayLabel(signName);
    final action = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Arquivar treinamento'),
        content: Text(
          'Escolha se deseja arquivar somente esta captura ou todas as suas '
          'sessões de $displayName. As gravações dos outros professores '
          'sempre serão preservadas.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, 'one'),
            child: const Text('Somente esta'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(dialogContext, 'all'),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Todas deste sinal'),
          ),
        ],
      ),
    );
    if (action == null || !mounted) return;
    if (action == 'all') {
      await _archiveAllMySamplesForSign(signName, displayName);
      return;
    }

    setState(() => _deletingSampleIds.add(id));
    try {
      final response = await _dio.delete(
        '/v1/training/my-samples/$id',
        options: _authorizedOptions,
      );
      if (!mounted || response.statusCode != 200) return;
      setState(() {
        _mySamples.removeWhere((item) => item['id'] == id);
      });
      _showSnackBar(
        'A sessão de $displayName foi excluída. As demais foram preservadas.',
        Colors.green,
      );
      _fetchSummary();
      final currentSign = _signNameController.text.trim();
      if (currentSign.isNotEmpty) _onSignNameChanged();
    } on DioException catch (error) {
      if (!mounted) return;
      _showSnackBar(
        error.response?.data?['detail']?.toString() ??
            'Não foi possível excluir esta sessão.',
        Colors.redAccent,
      );
    } finally {
      if (mounted) setState(() => _deletingSampleIds.remove(id));
    }
  }

  Future<void> _archiveAllMySamplesForSign(
    String signName,
    String displayName,
  ) async {
    final matchingIds = _mySamples
        .where((item) => item['sign_name'] == signName)
        .map((item) => item['id'] as String)
        .toSet();
    setState(() => _deletingSampleIds.addAll(matchingIds));
    try {
      final response = await _dio.delete(
        '/v1/training/my-signs',
        queryParameters: {'sign_name': signName},
        options: _authorizedOptions,
      );
      if (!mounted || response.statusCode != 200) return;
      final archivedCount =
          (response.data?['archived_count'] as num?)?.toInt() ?? 0;
      await Future.wait([_fetchMySamples(), _fetchSummary()]);
      if (!mounted) return;
      _showSnackBar(
        '$archivedCount sessões suas de $displayName foram arquivadas. '
        'Os outros professores foram preservados.',
        Colors.green,
      );
      final currentSign = _signNameController.text.trim();
      if (currentSign.isNotEmpty) _onSignNameChanged();
    } on DioException catch (error) {
      if (!mounted) return;
      _showSnackBar(
        error.response?.data?['detail']?.toString() ??
            'Não foi possível arquivar este sinal.',
        Colors.redAccent,
      );
    } finally {
      if (mounted) {
        setState(() => _deletingSampleIds.removeAll(matchingIds));
      }
    }
  }

  Future<void> _manageLegacySamples() async {
    final secretController = TextEditingController();
    final secret = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Gerenciamento administrativo'),
        content: TextField(
          controller: secretController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Código administrativo',
            prefixIcon: Icon(Icons.admin_panel_settings_outlined),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(dialogContext, secretController.text.trim()),
            child: const Text('Continuar'),
          ),
        ],
      ),
    );
    secretController.dispose();
    if (!mounted || secret == null || secret.isEmpty) return;

    final options = Options(
      headers: {'X-Trainer-Delete-Secret': secret},
    );
    try {
      final response = await _dio.get(
        '/v1/training/legacy-samples',
        options: options,
      );
      final samples = (response.data as List)
          .cast<Map<String, dynamic>>()
          .toList(growable: true);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('Capturas do sistema antigo'),
            content: SizedBox(
              width: 480,
              child: samples.isEmpty
                  ? const Text('Não existem capturas antigas ativas.')
                  : ListView.separated(
                      shrinkWrap: true,
                      itemCount: samples.length,
                      separatorBuilder: (_, __) => const Divider(),
                      itemBuilder: (context, index) {
                        final sample = samples[index];
                        final name = SignPhraseComposer.displayLabel(
                          sample['sign_name'] as String,
                        );
                        final trainer =
                            sample['trainer_name']?.toString().trim();
                        return ListTile(
                          title: Text(name),
                          subtitle: Text(
                            '${sample['frame_count']} quadros • '
                            '${trainer == null || trainer.isEmpty ? 'registro antigo' : trainer}',
                          ),
                          trailing: Semantics(
                            button: true,
                            label: 'Excluir captura antiga de $name',
                            child: IconButton(
                              tooltip: 'Excluir captura antiga',
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () async {
                                try {
                                  await _dio.delete(
                                    '/v1/training/legacy-samples/'
                                    '${sample['id']}',
                                    options: options,
                                  );
                                  if (!dialogContext.mounted) return;
                                  setDialogState(
                                    () => samples.removeAt(index),
                                  );
                                  _fetchSummary();
                                  _fetchMySamples();
                                } on DioException catch (error) {
                                  if (!mounted) return;
                                  _showSnackBar(
                                    error.response?.data?['detail']
                                            ?.toString() ??
                                        'Não foi possível excluir a captura.',
                                    Colors.redAccent,
                                  );
                                }
                              },
                            ),
                          ),
                        );
                      },
                    ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Fechar'),
              ),
            ],
          ),
        ),
      );
    } on DioException catch (error) {
      if (!mounted) return;
      _showSnackBar(
        error.response?.data?['detail']?.toString() ??
            'Não foi possível abrir os registros antigos.',
        Colors.redAccent,
      );
    }
  }

  String _formatCaptureDate(String rawDate) {
    final parsed = DateTime.tryParse(rawDate)?.toLocal();
    if (parsed == null) return 'Data indisponível';
    String twoDigits(int value) => value.toString().padLeft(2, '0');
    return '${twoDigits(parsed.day)}/${twoDigits(parsed.month)} '
        '${twoDigits(parsed.hour)}:${twoDigits(parsed.minute)}';
  }

  void _showSnackBar(String message, Color bgColor) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content:
            Text(message, style: const TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: bgColor,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Painel do Treinador - LibrAI'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: MediaQuery.sizeOf(context).width < 600 ? 12 : 24,
              vertical: 16,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Vídeo / Camera View Box
                Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 900),
                    child: SizedBox(
                      height: (MediaQuery.sizeOf(context).height * 0.68)
                          .clamp(460.0, 720.0),
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.black,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: _isRecording
                                ? Colors.redAccent
                                : (_holisticCaptureReady
                                    ? Colors.green
                                    : Colors.grey.shade800),
                            width: 3,
                          ),
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            if (kIsWeb)
                              const Positioned.fill(
                                child: HtmlElementView(
                                  viewType: 'mediapipe-video-view',
                                ),
                              )
                            else
                              const Center(
                                  child: Text("Câmera disponível no Web",
                                      style: TextStyle(color: Colors.white))),

                            Positioned(
                              top: 16,
                              left: 16,
                              child: Semantics(
                                liveRegion: true,
                                label: _holisticCaptureReady
                                    ? 'Captura válida. Mãos, rosto e tronco detectados.'
                                    : _trackingQuality == 'good' &&
                                            !_faceDetected
                                        ? 'Mostre o rosto inteiro.'
                                        : _trackingQuality == 'good' &&
                                                !_bodyDetected
                                            ? 'Mostre o tronco e os ombros.'
                                            : _trackingQuality == 'edge'
                                                ? 'Mão próxima da borda. Centralize as mãos.'
                                                : _trackingQuality == 'far'
                                                    ? 'Mãos distantes. Aproxime-se da câmera.'
                                                    : 'Aguardando detecção das mãos.',
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 14,
                                    vertical: 9,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.black.withOpacity(0.72),
                                    borderRadius: BorderRadius.circular(999),
                                    border: Border.all(
                                      color: _holisticCaptureReady
                                          ? const Color(0xFF00FFD1)
                                          : _trackingQuality == 'edge'
                                              ? const Color(0xFFFFD740)
                                              : _trackingQuality == 'far'
                                                  ? const Color(0xFF40C4FF)
                                                  : Colors.white70,
                                      width: 2,
                                    ),
                                    boxShadow: [
                                      BoxShadow(
                                        color: (_holisticCaptureReady
                                                ? const Color(0xFF00FFD1)
                                                : _trackingQuality == 'edge'
                                                    ? const Color(0xFFFFD740)
                                                    : _trackingQuality == 'far'
                                                        ? const Color(
                                                            0xFF40C4FF)
                                                        : Colors.white)
                                            .withOpacity(0.35),
                                        blurRadius: 12,
                                      ),
                                    ],
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(
                                        _holisticCaptureReady
                                            ? Icons.check_circle
                                            : _trackingQuality == 'edge'
                                                ? Icons.warning_amber_rounded
                                                : _trackingQuality == 'far'
                                                    ? Icons.zoom_in
                                                    : Icons
                                                        .pan_tool_alt_outlined,
                                        size: 20,
                                        color: _holisticCaptureReady
                                            ? const Color(0xFF00FFD1)
                                            : _trackingQuality == 'edge'
                                                ? const Color(0xFFFFD740)
                                                : _trackingQuality == 'far'
                                                    ? const Color(0xFF40C4FF)
                                                    : Colors.white,
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        _holisticCaptureReady
                                            ? 'CAPTURA VÁLIDA • MÃOS + ROSTO + TRONCO'
                                            : _trackingQuality == 'good' &&
                                                    !_faceDetected
                                                ? 'MOSTRE O ROSTO'
                                                : _trackingQuality == 'good' &&
                                                        !_bodyDetected
                                                    ? 'MOSTRE O TRONCO'
                                                    : _trackingQuality == 'edge'
                                                        ? 'CENTRALIZE AS MÃOS'
                                                        : _trackingQuality ==
                                                                'far'
                                                            ? 'APROXIME AS MÃOS'
                                                            : 'MOSTRE AS MÃOS',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.w800,
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),

                            Positioned(
                              left: 16,
                              bottom: 16,
                              child: Semantics(
                                label:
                                    'Desempenho da câmera: ${_inferenceFps.toStringAsFixed(1)} '
                                    'quadros por segundo, $_inferenceLatencyMs milissegundos.',
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 12,
                                    vertical: 7,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.black.withOpacity(0.68),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    '${_inferenceFps.toStringAsFixed(1)} FPS'
                                    '  •  $_inferenceLatencyMs ms'
                                    '${_handScreenRatio > 0 ? '  •  Mão $_handScreenRatio%' : ''}',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w700,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ),
                            ),

                            // Indicador de Gravação / Contagem
                            if (_isCountingDown)
                              CircleAvatar(
                                radius: 50,
                                backgroundColor: Colors.black54,
                                child: Text(
                                  "$_countdown",
                                  style: const TextStyle(
                                      fontSize: 48,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.white),
                                ),
                              ),
                            if (_isRecording)
                              Positioned(
                                top: 16,
                                right: 16,
                                child: Row(
                                  children: const [
                                    Icon(Icons.fiber_manual_record,
                                        color: Colors.redAccent, size: 24),
                                    SizedBox(width: 8),
                                    Text("GRAVANDO",
                                        style: TextStyle(
                                            color: Colors.redAccent,
                                            fontWeight: FontWeight.bold)),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                // Status / Dica de Enquadramento
                Text(
                  _statusMessage,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: _isRecording
                        ? Colors.redAccent
                        : theme.colorScheme.primary,
                  ),
                ),
                const SizedBox(height: 20),

                // Campo de Texto para nomear o Sinal
                TextField(
                  controller: _signNameController,
                  enabled: !_isRecording &&
                      !_isUploading &&
                      !_isCountingDown &&
                      _activeTrainingSign == null,
                  decoration: InputDecoration(
                    labelText: 'Nome do sinal (ex.: Obrigado)',
                    hintText: 'Digite a palavra correspondente',
                    prefixIcon: const Icon(Icons.label),
                    helperText: _isLoadingCount
                        ? 'Verificando banco de dados...'
                        : (SignPhraseComposer.trainingComponentsFor(
                                    _signNameController.text) !=
                                null
                            ? 'Expressão com dois sinais: grave cada palavra separadamente.'
                            : (SignPhraseComposer.normalizeLabel(
                                        _signNameController.text) ==
                                    'BOA'
                                ? 'BOA usa o mesmo gesto de BOM: treine somente BOM.'
                                : (_signNameController.text.trim().isNotEmpty
                                    ? (_activeTrainingSign != null
                                        ? 'Sessão em andamento: $_savedRepetitionsCount/$_requiredRepetitions repetições salvas no servidor. O nome fica travado até concluir.'
                                        : (_existingSamplesCount >= 30
                                            ? 'Meta atingida! $_existingSamplesCount/30 sessões gravadas.'
                                            : 'Sessões gravadas: $_existingSamplesCount/30. Cada professor fará 5 repetições sem redigitar o nome.'))
                                    : 'Digite o nome do sinal para ver o progresso do treino.'))),
                    helperStyle: TextStyle(
                      color: _existingSamplesCount >= 30
                          ? Colors.green
                          : theme.colorScheme.primary,
                      fontWeight: FontWeight.w500,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    filled: true,
                    fillColor:
                        theme.colorScheme.surfaceVariant.withOpacity(0.3),
                  ),
                  textCapitalization: TextCapitalization.sentences,
                ),
                const SizedBox(height: 20),

                // Botões de Ação
                if (_isUploading)
                  const Center(child: CircularProgressIndicator())
                else
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 60),
                      backgroundColor: _isRecording
                          ? Colors.redAccent
                          : theme.colorScheme.primary,
                      foregroundColor: theme.colorScheme.onPrimary,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    icon: Icon(_isRecording ? Icons.stop : Icons.videocam),
                    label: Text(
                      _isRecording
                          ? "Parar Gravação"
                          : (_activeTrainingSign == null
                              ? (_existingSamplesCount >= _requiredRepetitions
                                  ? "Gravar mais 5 repetições"
                                  : "Começar 5 repetições")
                              : (_hasPendingDraftUpload
                                  ? 'Tentar enviar repetição pendente'
                                  : "Gravar repetição ${_savedRepetitionsCount + 1}/$_requiredRepetitions")),
                      style: const TextStyle(
                          fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    onPressed: (_isCountingDown || _isUploading)
                        ? null
                        : (_isRecording
                            ? () => setState(() => _isRecording = false)
                            : _startRecordingFlow),
                  ),
                const SizedBox(height: 24),

                // Seção do Painel de Palavras Treinadas
                Card(
                  elevation: 0,
                  color: theme.colorScheme.surfaceVariant.withOpacity(0.3),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                    side: BorderSide(
                        color: theme.colorScheme.outline.withOpacity(0.2)),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.style,
                                    color: theme.colorScheme.primary),
                                const SizedBox(width: 8),
                                const Text(
                                  "Sinais Gravados na IA",
                                  style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                            IconButton(
                              icon: _isLoadingSummary
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2))
                                  : const Icon(Icons.refresh),
                              onPressed: _fetchSummary,
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        if (_trainedSignsSummary.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 12.0),
                            child: Text(
                              "Nenhum sinal gravado ainda. Digite o nome acima e clique em Começar Captura para registrar o primeiro sinal!",
                              style: TextStyle(color: Colors.grey),
                            ),
                          )
                        else
                          ListView.separated(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: _trainedSignsSummary.length,
                            separatorBuilder: (_, __) =>
                                const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final item = _trainedSignsSummary[index];
                              final String name =
                                  item['sign_name'] ?? 'SEU_SINAL';
                              final int count = item['count'] ?? 0;
                              final bool isComplete = count >= 30;

                              return ListTile(
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 4, vertical: 2),
                                title: Text(
                                  SignPhraseComposer.displayLabel(name),
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 16),
                                ),
                                subtitle: Text(
                                  isComplete
                                      ? "$count/30 sessões (meta atingida)"
                                      : "$count/30 sessões",
                                  style: TextStyle(
                                    color: isComplete
                                        ? Colors.green
                                        : Colors.orange,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 10,
                                        vertical: 4,
                                      ),
                                      decoration: BoxDecoration(
                                        color: isComplete
                                            ? Colors.green.withOpacity(0.15)
                                            : Colors.orange.withOpacity(0.15),
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Text(
                                        "$count",
                                        style: TextStyle(
                                          color: isComplete
                                              ? Colors.green
                                              : Colors.orange,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            },
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Card(
                  elevation: 0,
                  color: theme.colorScheme.surfaceVariant.withOpacity(0.3),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                    side: BorderSide(
                      color: theme.colorScheme.outline.withOpacity(0.2),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.person_pin_outlined,
                              color: theme.colorScheme.primary,
                            ),
                            const SizedBox(width: 8),
                            const Expanded(
                              child: Text(
                                'Minhas sessões',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            Semantics(
                              button: true,
                              label: 'Atualizar minhas sessões de treinamento',
                              child: IconButton(
                                onPressed: _isLoadingMySamples
                                    ? null
                                    : _fetchMySamples,
                                icon: _isLoadingMySamples
                                    ? const SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : const Icon(Icons.refresh),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Toque na lixeira vermelha para arquivar uma captura '
                          'ou todas as suas sessões daquele sinal.',
                          style: TextStyle(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            onPressed: _manageLegacySamples,
                            icon: const Icon(Icons.history),
                            label: const Text(
                              'Administração: registros do sistema antigo',
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        if (_mySamples.isEmpty && !_isLoadingMySamples)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 12),
                            child: Text(
                              'Você ainda não enviou nenhuma sessão nesta conta.',
                            ),
                          )
                        else
                          ListView.separated(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: _mySamples.length,
                            separatorBuilder: (_, __) =>
                                const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final sample = _mySamples[index];
                              final id = sample['id'] as String;
                              final name = sample['sign_name'] as String;
                              final frames = sample['frame_count'] as int;
                              final deleting = _deletingSampleIds.contains(id);
                              return ListTile(
                                minTileHeight: 64,
                                contentPadding:
                                    const EdgeInsets.symmetric(horizontal: 4),
                                title: Text(
                                  SignPhraseComposer.displayLabel(name),
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                subtitle: Text(
                                  '$frames quadros • '
                                  '${_formatCaptureDate(
                                    sample['created_at'] as String,
                                  )}',
                                ),
                                trailing: Semantics(
                                  button: true,
                                  label:
                                      'Excluir minha sessão de treinamento de '
                                      '${SignPhraseComposer.displayLabel(name)}',
                                  child: IconButton(
                                    tooltip: 'Excluir esta sessão',
                                    onPressed: deleting
                                        ? null
                                        : () => _confirmDeleteMySample(sample),
                                    icon: deleting
                                        ? const SizedBox(
                                            width: 20,
                                            height: 20,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                            ),
                                          )
                                        : Icon(
                                            Icons.delete_outline,
                                            color: theme.colorScheme.error,
                                          ),
                                  ),
                                ),
                              );
                            },
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
