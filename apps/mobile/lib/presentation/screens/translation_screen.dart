import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../platform/mediapipe_interop.dart';
import '../../domain/vision_validator.dart';
import '../state/landmark_buffer.dart';

class TranslationScreen extends StatefulWidget {
  const TranslationScreen({super.key});

  @override
  State<TranslationScreen> createState() => _TranslationScreenState();
}

class _TranslationScreenState extends State<TranslationScreen> {
  final MediaPipeService _visionService = MediaPipeService();
  final LandmarkBuffer _frameBuffer = LandmarkBuffer(maxFrames: 30);
  Timer? _processingTimer;

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
    // Inicia serviço de landmarks
    _visionService.start();

    // Loop de processamento de quadros a ~30 FPS (a cada 33ms)
    _processingTimer = Timer.periodic(const Duration(milliseconds: 33), (timer) {
      if (!_isTranslating) return;

      final landmarks = _visionService.getLatestLandmarks();
      final handsOk = _visionService.isHandsDetected();
      final faceOk = _visionService.isFaceDetected();
      final bodyOk = _visionService.isBodyDetected();

      // Validação de enquadramento
      final framing = VisionValidator.validateFraming(landmarks, faceOk);

      // Buffer e backpressure
      if (framing == VisionState.ok) {
        _frameBuffer.addFrame(landmarks);
      }

      setState(() {
        _handsDetected = handsOk;
        _faceDetected = faceOk;
        _bodyDetected = bodyOk;
        _framingState = framing;

        // Simulação de tradução se enquadramento estiver perfeito e houver dados
        if (framing == VisionState.ok && _frameBuffer.currentSize > 10) {
          _partialText = "Sinalização detectada...";
          _finalText = "Tudo bem";
          _confidence = 0.96;
        } else if (framing == VisionState.waitingPerson) {
          _partialText = "Aguardando sinalização...";
          _confidence = 0.0;
        }
      });
    });
  }

  @override
  void dispose() {
    _processingTimer?.cancel();
    _visionService.stop();
    _frameBuffer.clear();
    super.dispose();
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
            icon: const Icon(Icons.flip_camera_android),
            semanticsLabel: 'Alternar câmera frontal/traseira',
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
                      // Moldura de enquadramento
                      Container(
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: _framingState == VisionState.ok ? Colors.green.withOpacity(0.5) : Colors.red.withOpacity(0.5),
                            width: 3.0,
                          ),
                        ),
                      ),
                      
                      // Câmera Placeholder
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
                        icon: const Icon(Icons.volume_up),
                        semanticsLabel: 'Ouvir tradução em voz',
                        onPressed: () {
                          // Síntese de voz
                        },
                      ),
                    ],
                  ),
                  const Spacer(),
                  
                  // Controles de Ação
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      IconButton.filledTonal(
                        icon: Icon(_isTranslating ? Icons.pause : Icons.play_arrow),
                        semanticsLabel: _isTranslating ? 'Pausar tradução' : 'Retomar tradução',
                        onPressed: () {
                          setState(() {
                            _isTranslating = !_isTranslating;
                          });
                        },
                      ),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.edit),
                        label: const Text('Corrigir'),
                        onPressed: () {
                          // Modal de correção
                        },
                      ),
                      IconButton.filledTonal(
                        icon: const Icon(Icons.stop),
                        color: Colors.redAccent,
                        semanticsLabel: 'Encerrar tradução',
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
      padding: const EdgeInsets.symmetric(horizontal: 10, py: 4),
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
