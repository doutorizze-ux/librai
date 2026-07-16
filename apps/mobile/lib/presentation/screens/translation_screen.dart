import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';
import '../../platform/mediapipe_interop.dart';
import '../../domain/vision_validator.dart';
import '../state/landmark_buffer.dart';
import '../../platform/mock_interpreter.dart';
import '../../platform/tts_service.dart';
import '../../platform/local_translator.dart';

class TranslationScreen extends StatefulWidget {
  const TranslationScreen({super.key});

  @override
  State<TranslationScreen> createState() => _TranslationScreenState();
}

class _TranslationScreenState extends State<TranslationScreen> {
  final MediaPipeService _visionService = MediaPipeService();
  final LandmarkBuffer _frameBuffer = LandmarkBuffer(maxFrames: 30);
  final TtsService _ttsService = TtsService();
  final MockSignInterpreter _interpreter = MockSignInterpreter();
  final LocalLibrasTranslator _translator = LocalLibrasTranslator();
  Timer? _processingTimer;
  final List<String> _spellingBuffer = [];
  Timer? _spellingEndTimer;
  final List<String> _predictionHistory = [];

  bool _isTranslating = true;
  String _partialText = "Aguardando sinalização...";
  String _finalText = "";
  double _confidence = 0.0;
  
  bool _handsDetected = false;
  bool _faceDetected = false;
  bool _bodyDetected = false;
  VisionState _framingState = VisionState.waitingPerson;

  @override
  void initState() {
    super.initState();
    // Registrar view da câmera no web antes de iniciar
    _visionService.registerVideoView();
    // Inicia serviço de landmarks
    _visionService.start();
    // Inicializar interpretador simulado
    _interpreter.loadModel("weights.json");

    // Loop de processamento de quadros a ~30 FPS (a cada 33ms)
    _processingTimer = Timer.periodic(const Duration(milliseconds: 33), (timer) {
      if (!_isTranslating) return;

      final landmarks = _visionService.getLatestLandmarks();
      final handsOk = _visionService.isHandsDetected();
      final faceOk = _visionService.isFaceDetected();
      final bodyOk = _visionService.isBodyDetected();

      // Validação de enquadramento
      final framing = VisionValidator.validateFraming(landmarks, faceOk);

      setState(() {
        _handsDetected = handsOk;
        _faceDetected = faceOk;
        _bodyDetected = bodyOk;
        _framingState = framing;
      });

      // Processamento assíncrono do frame
      _processFrame(landmarks, faceOk, handsOk, bodyOk, framing);
    });
  }

  bool _isSpellingUnit(String label) {
    final clean = label.trim().toUpperCase();
    if (clean.isEmpty) return false;
    
    // Se for uma única letra (A-Z)
    if (clean.length == 1 && RegExp(r'[A-Z]').hasMatch(clean)) {
      return true;
    }
    
    // Lista de palavras curtas conhecidas que NÃO são sílabas
    final knownWords = {'SIM', 'NÃO', 'OLÁ', 'RUA', 'SUS', 'CPF', 'RG'};
    if (clean.length <= 3 && !knownWords.contains(clean)) {
      return true;
    }
    
    // Sílabas conhecidas
    final knownSyllables = {'FRE', 'DE', 'RI', 'CO', 'BO', 'MA', 'TA', 'RA', 'PA', 'LI', 'AI'};
    if (knownSyllables.contains(clean)) {
      return true;
    }
    
    return false;
  }

  Future<void> _processFrame(List<Map<String, double>>? landmarks, bool faceOk, bool handsOk, bool bodyOk, VisionState framing) async {
    if (framing == VisionState.ok && landmarks != null && landmarks.isNotEmpty) {
      _frameBuffer.addFrame(landmarks);

      // Se acumulou frames e o interpretador não está ocupado
      if (_frameBuffer.currentSize >= 15 && !_frameBuffer.isProcessing) {
        _frameBuffer.setProcessing(true);
        try {
          final prediction = await _interpreter.predict(landmarks);
          
          // Adicionar a predição no histórico de votos para suavizar e evitar oscilações
          _predictionHistory.add(prediction.label);
          if (_predictionHistory.length > 3) {
            _predictionHistory.removeAt(0);
          }
          
          // Encontrar a classe mais votada (Moda) no histórico
          final Map<String, int> votes = {};
          for (final label in _predictionHistory) {
            votes[label] = (votes[label] ?? 0) + 1;
          }
          
          String votedLabel = prediction.label;
          int maxVotes = 0;
          votes.forEach((key, val) {
            if (val > maxVotes) {
              maxVotes = val;
              votedLabel = key;
            }
          });
          
          // Exigir pelo menos 2 votos de consistência se tivermos histórico suficiente
          final requiredVotes = _predictionHistory.length < 2 ? 1 : 2;
          
          if (maxVotes >= requiredVotes && votedLabel != "SINAL_DESCONHECIDO" && votedLabel != "DADOS_INSUFICIENTES") {
            if (_isSpellingUnit(votedLabel)) {
              // Cancelar timer de finalização anterior
              _spellingEndTimer?.cancel();
              
              // Evitar duplicar a mesma sílaba se for detectada repetida muito rápido
              if (_spellingBuffer.isEmpty || _spellingBuffer.last != votedLabel) {
                _spellingBuffer.add(votedLabel);
                
                // Mostrar progresso (ex: F-R-E ou FRE-DE)
                final separator = votedLabel.length == 1 ? "" : "-";
                final progressText = _spellingBuffer.join(separator);
                setState(() {
                  _partialText = "Soletrando: $progressText";
                  _confidence = prediction.confidence;
                });
              }
              
              // Agendar a finalização da palavra soletrada (1.5 segundos sem novos sinais)
              _spellingEndTimer = Timer(const Duration(milliseconds: 1500), () async {
                if (_spellingBuffer.isNotEmpty) {
                  final fullWord = _spellingBuffer.join("");
                  setState(() {
                    _partialText = "Palavra soletrada";
                    _finalText = fullWord;
                  });
                  await _ttsService.speak(fullWord);
                  _spellingBuffer.clear();
                }
              });
            } else {
              // Se tinha alguma soletragem em andamento, finaliza ela primeiro
              if (_spellingBuffer.isNotEmpty) {
                _spellingEndTimer?.cancel();
                final fullWord = _spellingBuffer.join("");
                setState(() {
                  _finalText = fullWord;
                });
                await _ttsService.speak(fullWord);
                _spellingBuffer.clear();
              }

              // Processamento de palavra/sinal completo
              final translation = await _translator.translate([votedLabel], sessionId: "session_live");
              
              if (translation.isNotEmpty && translation != _finalText) {
                setState(() {
                  _partialText = "Sinal detectado: $votedLabel";
                  _finalText = translation;
                  _confidence = prediction.confidence;
                });
                
                // Falar a tradução via TTS
                await _ttsService.speak(translation);
              }
            }
          }
        } catch (e) {
          debugPrint("Erro no processamento do sinal: $e");
        } finally {
          _frameBuffer.setProcessing(false);
          _frameBuffer.clear();
        }
      }
    } else if (framing == VisionState.waitingPerson) {
      _predictionHistory.clear();
      setState(() {
        _partialText = "Aguardando sinalização...";
        _confidence = 0.0;
      });
    }
  }

  @override
  void dispose() {
    _processingTimer?.cancel();
    _spellingEndTimer?.cancel();
    _predictionHistory.clear();
    _visionService.stop();
    _frameBuffer.clear();
    super.dispose();
  }

  void _showCorrectionDialog() {
    final controller = TextEditingController(text: _finalText);
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Row(
            children: [
              Icon(Icons.edit),
              SizedBox(width: 8),
              Text("Corrigir Tradução"),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("Ajuste o texto traduzido abaixo:"),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                maxLines: 3,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: "Digite a tradução correta...",
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text("Cancelar"),
            ),
            ElevatedButton(
              onPressed: () async {
                final corrected = controller.text.trim();
                if (corrected.isNotEmpty) {
                  setState(() {
                    _finalText = corrected;
                  });
                  Navigator.pop(context);
                  await _ttsService.speak(corrected);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text("Tradução corrigida com sucesso!"),
                      backgroundColor: Colors.green,
                    ),
                  );
                }
              },
              child: const Text("Confirmar"),
            ),
          ],
        );
      },
    );
  }

  String _getWarningMessage(VisionState state) {
    switch (state) {
      case VisionState.waitingPerson:
        return "Aguardando pessoa sinalizadora...";
      case VisionState.adjustFraming:
        return "Ajuste o enquadramento (centralize-se)";
      case VisionState.stepBack:
        return "Afaste-se da câmera";
      case VisionState.stepCloser:
        return "Aproxime-se da câmera";
      case VisionState.insufficientLighting:
        return "Iluminação insuficiente";
      case VisionState.handsOutOfFrame:
        return "Mãos fora do enquadramento";
      case VisionState.faceOutOfFrame:
        return "Rosto fora do enquadramento";
      case VisionState.ok:
        return "Enquadramento Correto";
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tradução ao Vivo'),
        actions: [
          IconButton(
            icon: Semantics(
              label: 'Alternar câmera frontal/traseira',
              child: const Icon(Icons.flip_camera_android),
            ),
            onPressed: () {
              // Alterna câmera
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Área da Câmera
          Expanded(
            flex: 3,
            child: Padding(
              padding: const EdgeInsets.all(12.0),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16.0),
                child: Container(
                  color: Colors.black87,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Renders live webcam stream on web
                      if (kIsWeb)
                        const Positioned.fill(
                          child: HtmlElementView(viewType: 'mediapipe-video-view'),
                        ),

                      // Moldura de enquadramento
                      Container(
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: _framingState == VisionState.ok ? Colors.green.withOpacity(0.5) : Colors.red.withOpacity(0.5),
                            width: 3.0,
                          ),
                        ),
                      ),
                      
                      // Câmera Placeholder (só mostra o ícone de pessoa se não for web)
                      if (!kIsWeb)
                        Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.person, color: theme.colorScheme.primary.withOpacity(0.3), size: 100),
                            const SizedBox(height: 8),
                            Text(
                              _getWarningMessage(_framingState),
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),

                      if (kIsWeb)
                        Positioned(
                          bottom: 16,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: Colors.black54,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              _getWarningMessage(_framingState),
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12),
                            ),
                          ),
                        ),
                      
                      // Status de landmarks
                      Positioned(
                        top: 16,
                        left: 16,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _buildLandmarkChip('Mãos', _handsDetected),
                            const SizedBox(height: 4),
                            _buildLandmarkChip('Rosto', _faceDetected),
                            const SizedBox(height: 4),
                            _buildLandmarkChip('Tronco', _bodyDetected),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          
          // Legenda e Painel de Controle
          Expanded(
            flex: 2,
            child: Container(
              padding: const EdgeInsets.all(24.0),
              decoration: BoxDecoration(
                color: theme.colorScheme.surface,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(24.0),
                  topRight: Radius.circular(24.0),
                ),
                boxShadow: const [
                  BoxShadow(
                    color: Colors.black12,
                    blurRadius: 10,
                    offset: Offset(0, -4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Legenda Parcial
                  Text(
                    _partialText,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  const SizedBox(height: 8),
                  
                  // Legenda Consolidada
                  Text(
                    _finalText.isNotEmpty ? _finalText : "Sinalize em frente à câmera",
                    style: theme.textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  
                  // Nível de Confiança
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(
                            _confidence >= 0.8 ? Icons.verified : Icons.warning_amber_rounded,
                            color: _confidence >= 0.8 ? Colors.green : Colors.orange,
                          ),
                          const SizedBox(width: 8),
                          Text(_confidence > 0.0 ? 'Confiança: ${(_confidence * 100).toStringAsFixed(0)}%' : 'Sem sinalização ativa'),
                        ],
                      ),
                      IconButton(
                        icon: Semantics(
                          label: 'Ouvir tradução em voz',
                          child: const Icon(Icons.volume_up),
                        ),
                        onPressed: _finalText.isNotEmpty
                            ? () => _ttsService.speak(_finalText)
                            : null,
                      ),
                    ],
                  ),
                  const Spacer(),
                  
                  // Controles de Ação
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      IconButton.filledTonal(
                        icon: Semantics(
                          label: _isTranslating ? 'Pausar tradução' : 'Retomar tradução',
                          child: Icon(_isTranslating ? Icons.pause : Icons.play_arrow),
                        ),
                        onPressed: () {
                          setState(() {
                            _isTranslating = !_isTranslating;
                          });
                        },
                      ),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.edit),
                        label: const Text('Corrigir'),
                        onPressed: _showCorrectionDialog,
                      ),
                      IconButton.filledTonal(
                        icon: Semantics(
                          label: 'Encerrar tradução',
                          child: const Icon(Icons.stop),
                        ),
                        color: Colors.redAccent,
                        onPressed: () => context.pop(),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLandmarkChip(String label, bool detected) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: detected ? Colors.green.withOpacity(0.8) : Colors.red.withOpacity(0.8),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$label: ${detected ? "Ok" : "Ausente"}',
        style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
      ),
    );
  }
}
