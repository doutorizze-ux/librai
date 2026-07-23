import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';
import 'package:dio/dio.dart';
import '../../platform/mediapipe_interop.dart';
import '../../platform/tts_service.dart';

class TrainerScreen extends StatefulWidget {
  const TrainerScreen({super.key});

  @override
  State<TrainerScreen> createState() => _TrainerScreenState();
}

class _TrainerScreenState extends State<TrainerScreen> {
  final MediaPipeService _visionService = MediaPipeService();
  final TtsService _ttsService = TtsService();
  final Dio _dio = Dio(BaseOptions(
    baseUrl: const String.fromEnvironment('API_URL', defaultValue: 'https://api.tvcatolica.site'),
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
  bool _handsDetected = false;
  String _statusMessage = "Posicione a mão em frente à câmera";
  bool _isUploading = false;

  Timer? _debounceTimer;
  int _existingSamplesCount = 0;
  bool _isLoadingCount = false;
  List<Map<String, dynamic>> _trainedSignsSummary = [];
  bool _isLoadingSummary = false;

  @override
  void initState() {
    super.initState();
    _visionService.registerVideoView();
    _visionService.start();

    _signNameController.addListener(_onSignNameChanged);
    _fetchSummary();

    // Loop de monitoramento de mão (apenas para feedback visual do frame)
    _frameTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) {
      if (!mounted) return;
      final handsOk = _visionService.isHandsDetected();
      setState(() {
        _handsDetected = handsOk;
      });
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
    final text = _signNameController.text.trim().toUpperCase();
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
          options: Options(
            headers: {
              'X-Trainer-Secret': 'librAI_trainer_secret_2026',
            },
          ),
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
  void _startRecordingFlow() {
    final signName = _signNameController.text.trim().toUpperCase();
    if (signName.isEmpty) {
      _showSnackBar("Por favor, digite o nome do sinal (ex: OBRIGADO)", Colors.redAccent);
      return;
    }

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

  // Captura dos frames de landmarks durante 2 segundos
  void _startCapture(String signName) {
    setState(() {
      _isRecording = true;
      _recordedLandmarks.clear();
      _statusMessage = "Gravando sinal: $signName";
    });

    int frameCount = 0;
    Timer.periodic(const Duration(milliseconds: 33), (timer) async {
      if (!mounted || !_isRecording) {
        timer.cancel();
        return;
      }

      final latest = _visionService.getLatestLandmarks();
      if (latest != null && latest.isNotEmpty) {
        // Acumular todos os pontos no dataset do sinal
        _recordedLandmarks.addAll(latest);
      }

      frameCount++;
      if (frameCount >= 60) {
        timer.cancel();
        _stopAndUploadCapture(signName);
      }
    });
  }

  // Finaliza a gravação e envia para a API do Coolify
  Future<void> _stopAndUploadCapture(String signName) async {
    setState(() {
      _isRecording = false;
      _isUploading = true;
      _statusMessage = "Enviando dados para o servidor...";
    });

    if (_recordedLandmarks.isEmpty) {
      setState(() {
        _isUploading = false;
        _statusMessage = "Nenhum movimento capturado. Tente novamente.";
      });
      _showSnackBar("Erro: Nenhum landmark capturado na câmera.", Colors.redAccent);
      return;
    }

    try {
      final response = await _dio.post(
        '/v1/training/samples',
        options: Options(
          headers: {
            'X-Trainer-Secret': 'librAI_trainer_secret_2026',
          },
        ),
        data: {
          'sign_name': signName,
          'landmarks': _recordedLandmarks,
        },
      );

      if (response.statusCode == 201) {
        setState(() {
          _statusMessage = "Sinal '$signName' enviado com sucesso!";
          _signNameController.clear();
          _existingSamplesCount = 0;
          _isLoadingCount = false;
        });
        _ttsService.speak("Sinal gravado com sucesso!");
        _showSnackBar("Sinal enviado com sucesso para a base da IA!", Colors.green);
        _fetchSummary();
      }
    } catch (e) {
      debugPrint("Erro ao enviar dados de treino: $e");
      setState(() {
        _statusMessage = "Falha ao enviar sinal. Verifique a conexão.";
      });
      _showSnackBar("Falha de conexão com o servidor Coolify.", Colors.redAccent);
    } finally {
      setState(() {
        _isUploading = false;
      });
    }
  }

  Future<void> _fetchSummary() async {
    setState(() => _isLoadingSummary = true);
    try {
      final response = await _dio.get(
        '/v1/training/samples/summary',
        options: Options(
          headers: {'X-Trainer-Secret': 'librAI_trainer_secret_2026'},
        ),
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

  Future<void> _deleteSignSamples(String signName) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text("Refazer Sinal '$signName'?"),
        content: Text("Isso apagará todas as amostras gravadas de '$signName' para que você possa regravar do zero."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Cancelar")),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent, foregroundColor: Colors.white),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text("Apagar e Refazer"),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      final response = await _dio.delete(
        '/v1/training/samples/$signName',
        options: Options(
          headers: {'X-Trainer-Secret': 'librAI_trainer_secret_2026'},
        ),
      );
      if (mounted && response.statusCode == 200) {
        _showSnackBar("Amostras de '$signName' apagadas! Pronto para regravar.", Colors.orange);
        _signNameController.text = signName;
        _fetchSummary();
      }
    } catch (e) {
      _showSnackBar("Erro ao apagar amostras.", Colors.redAccent);
    }
  }

  void _showSnackBar(String message, Color bgColor) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message, style: const TextStyle(fontWeight: FontWeight.bold)),
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
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Vídeo / Camera View Box
                SizedBox(
                  height: 320,
                  child: Container(
                  decoration: BoxDecoration(
                    color: Colors.black,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: _isRecording 
                          ? Colors.redAccent 
                          : (_handsDetected ? Colors.green : Colors.grey.shade800),
                      width: 3,
                    ),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      if (kIsWeb)
                        const HtmlElementView(viewType: 'mediapipe-video-view')
                      else
                        const Center(child: Text("Câmera disponível no Web", style: TextStyle(color: Colors.white))),
                      
                      // Indicador de Gravação / Contagem
                      if (_isCountingDown)
                        CircleAvatar(
                          radius: 50,
                          backgroundColor: Colors.black54,
                          child: Text(
                            "$_countdown",
                            style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold, color: Colors.white),
                          ),
                        ),
                      if (_isRecording)
                        Positioned(
                          top: 16,
                          right: 16,
                          child: Row(
                            children: const [
                              Icon(Icons.fiber_manual_record, color: Colors.redAccent, size: 24),
                              SizedBox(width: 8),
                              Text("GRAVANDO", style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold)),
                            ],
                          ),
                        ),
                    ],
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
                  color: _isRecording ? Colors.redAccent : theme.colorScheme.primary,
                ),
              ),
              const SizedBox(height: 20),

              // Campo de Texto para nomear o Sinal
              TextField(
                controller: _signNameController,
                enabled: !_isRecording && !_isUploading && !_isCountingDown,
                decoration: InputDecoration(
                  labelText: 'Nome do Sinal (ex: OBRIGADO)',
                  hintText: 'Digite a palavra correspondente',
                  prefixIcon: const Icon(Icons.label),
                  helperText: _isLoadingCount
                      ? 'Verificando banco de dados...'
                      : (_signNameController.text.trim().isNotEmpty
                          ? (_existingSamplesCount >= 30
                              ? 'Meta atingida! $_existingSamplesCount/30 amostras gravadas (Excelente!).'
                              : 'Amostras gravadas: $_existingSamplesCount/30 (Grave mais para maior precisão).')
                          : 'Digite o nome do sinal para ver o progresso do treino.'),
                  helperStyle: TextStyle(
                    color: _existingSamplesCount >= 30 ? Colors.green : theme.colorScheme.primary,
                    fontWeight: FontWeight.w500,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  filled: true,
                  fillColor: theme.colorScheme.surfaceVariant.withOpacity(0.3),
                ),
                textCapitalization: TextCapitalization.characters,
              ),
              const SizedBox(height: 20),

              // Botões de Ação
              if (_isUploading)
                const Center(child: CircularProgressIndicator())
              else
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 60),
                    backgroundColor: _isRecording ? Colors.redAccent : theme.colorScheme.primary,
                    foregroundColor: theme.colorScheme.onPrimary,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  icon: Icon(_isRecording ? Icons.stop : Icons.videocam),
                  label: Text(
                    _isRecording ? "Parar Gravação" : "Começar Captura",
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  onPressed: (_isCountingDown || _isUploading)
                      ? null 
                      : (_isRecording ? () => setState(() => _isRecording = false) : _startRecordingFlow),
                ),
              const SizedBox(height: 24),

              // Seção do Painel de Palavras Treinadas
              Card(
                elevation: 0,
                color: theme.colorScheme.surfaceVariant.withOpacity(0.3),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                  side: BorderSide(color: theme.colorScheme.outline.withOpacity(0.2)),
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
                              Icon(Icons.style, color: theme.colorScheme.primary),
                              const SizedBox(width: 8),
                              const Text(
                                "Sinais Gravados na IA",
                                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                          IconButton(
                            icon: _isLoadingSummary
                                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
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
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final item = _trainedSignsSummary[index];
                            final String name = item['sign_name'] ?? 'SEU_SINAL';
                            final int count = item['count'] ?? 0;
                            final bool isComplete = count >= 30;

                            return ListTile(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                              title: Text(
                                name,
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                              ),
                              subtitle: Text(
                                isComplete ? "$count/30 amostras (Excelente!)" : "$count/30 amostras",
                                style: TextStyle(
                                  color: isComplete ? Colors.green : Colors.orange,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                              trailing: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.horizontal(10, 4),
                                    decoration: BoxDecoration(
                                      color: isComplete ? Colors.green.withOpacity(0.15) : Colors.orange.withOpacity(0.15),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      "$count",
                                      style: TextStyle(
                                        color: isComplete ? Colors.green : Colors.orange,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  IconButton(
                                    icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                                    tooltip: "Refazer / Apagar",
                                    onPressed: () => _deleteSignSamples(name),
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
            ],
          ),
        ),
      ),
    );
  }
}
