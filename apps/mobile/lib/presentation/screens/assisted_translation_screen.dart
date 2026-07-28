import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/remote_assisted_sign_interpreter.dart';
import '../../domain/entities/assisted_prediction.dart';
import '../../domain/interfaces/assisted_sign_interpreter.dart';
import '../../domain/sign_phrase_composer.dart';
import '../../platform/mediapipe_interop.dart';
import '../../platform/tts_service.dart';

class AssistedTranslationScreen extends StatefulWidget {
  const AssistedTranslationScreen({
    super.key,
    this.interpreter,
    this.visionService,
  });

  final AssistedSignInterpreter? interpreter;
  final MediaPipeService? visionService;

  @override
  State<AssistedTranslationScreen> createState() =>
      _AssistedTranslationScreenState();
}

class _AssistedTranslationScreenState extends State<AssistedTranslationScreen> {
  late final AssistedSignInterpreter _interpreter;
  late final MediaPipeService _visionService;
  final TtsService _ttsService = TtsService();
  final SignPhraseComposer _phraseComposer = SignPhraseComposer();
  final List<Map<String, dynamic>> _frames = [];
  Timer? _captureTimer;
  int _lastRevision = -1;
  bool _capturing = false;
  bool _submitting = false;
  String? _error;
  String? _selectedLabel;
  String? _translatedText;
  List<AssistedPredictionCandidate> _candidates = const [];

  @override
  void initState() {
    super.initState();
    _interpreter = widget.interpreter ?? RemoteAssistedSignInterpreter();
    _visionService = widget.visionService ?? MediaPipeService();
    _visionService.registerVideoView();
    _visionService.start();
    _captureTimer = Timer.periodic(
      const Duration(milliseconds: 33),
      (_) => _collectFrame(),
    );
  }

  void _collectFrame() {
    if (!_capturing || _submitting) return;
    final revision = _visionService.getLandmarkRevision();
    if (revision == _lastRevision) return;
    _lastRevision = revision;
    final frame = _visionService.getLatestHandFrame();
    if (frame == null || frame['hands'] is! List) return;
    final hands = frame['hands'] as List;
    if (hands.isEmpty) return;
    if (_frames.length >= 180) {
      unawaited(_finishCapture());
      return;
    }
    _frames.add(Map<String, dynamic>.from(frame));
    if (mounted && _frames.length % 5 == 0) setState(() {});
  }

  void _startCapture() {
    _ttsService.unlock();
    setState(() {
      _frames.clear();
      _candidates = const [];
      _selectedLabel = null;
      _error = null;
      _capturing = true;
      _lastRevision = -1;
    });
  }

  void _cancelCapture() {
    setState(() {
      _capturing = false;
      _frames.clear();
      _error = null;
    });
  }

  Future<void> _finishCapture() async {
    if (!_capturing || _submitting) return;
    setState(() => _capturing = false);
    if (_frames.length < 12) {
      setState(() {
        _error =
            'Poucos quadros válidos. Mostre as mãos e repita o sinal inteiro.';
        _frames.clear();
      });
      return;
    }
    final capturedFrames = List<Map<String, dynamic>>.from(_frames);
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final result = await _interpreter.predict(capturedFrames);
      if (!mounted) return;
      setState(() {
        _candidates = result.candidates;
        _submitting = false;
        _frames.clear();
        if (_candidates.isEmpty) {
          _error = 'O modelo não encontrou uma opção para este sinal.';
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _frames.clear();
        _error =
            'Não foi possível analisar agora. Verifique a conexão e tente novamente.';
      });
    }
  }

  Future<void> _selectCandidate(AssistedPredictionCandidate candidate) async {
    _phraseComposer.releaseCurrentSign();
    final composition = _phraseComposer.accept(candidate.label);
    setState(() {
      _selectedLabel = candidate.label;
      _translatedText =
          composition?.text ?? SignPhraseComposer.displayLabel(candidate.label);
    });
    if (composition?.isFinal == true) {
      await _ttsService.speak(composition!.text);
    }
  }

  @override
  void dispose() {
    _captureTimer?.cancel();
    _visionService.stop();
    _frames.clear();
    _phraseComposer.reset();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final topInset = MediaQuery.paddingOf(context).top;
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          ColoredBox(
            color: const Color(0xFF111318),
            child: kIsWeb
                ? const HtmlElementView(viewType: 'mediapipe-video-view')
                : const Center(
                    child: Icon(
                      Icons.back_hand_outlined,
                      color: Colors.white38,
                      size: 112,
                    ),
                  ),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xAA000000),
                  Color(0x00000000),
                  Color(0x22000000),
                  Color(0xE8000000),
                ],
                stops: [0, 0.28, 0.55, 1],
              ),
            ),
          ),
          Positioned(
            top: topInset + 8,
            left: 12,
            right: 12,
            child: Row(
              children: [
                Semantics(
                  button: true,
                  label: 'Voltar ao início',
                  child: IconButton.filledTonal(
                    tooltip: 'Voltar',
                    onPressed: () => context.go('/'),
                    icon: const Icon(Icons.arrow_back),
                  ),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    'Piloto • energia',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                if (_capturing)
                  Semantics(
                    liveRegion: true,
                    label: 'Captura ativa',
                    child: _statusPill('CAPTURANDO', const Color(0xFFD9364F)),
                  ),
              ],
            ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: SafeArea(
              top: false,
              minimum: const EdgeInsets.fromLTRB(16, 16, 16, 20),
              child: Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: const Color(0xF51B1820),
                  borderRadius: BorderRadius.circular(26),
                  border: Border.all(color: Colors.white24),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      _instruction,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        height: 1.3,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (_capturing) ...[
                      const SizedBox(height: 8),
                      Text(
                        '${_frames.length} quadros válidos',
                        style: const TextStyle(color: Colors.white70),
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 10),
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
                    if (_candidates.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      for (final candidate in _candidates)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Semantics(
                            button: true,
                            label:
                                '${SignPhraseComposer.displayLabel(candidate.label)}, possibilidade ${(candidate.confidence * 100).round()} por cento',
                            child: OutlinedButton(
                              style: OutlinedButton.styleFrom(
                                minimumSize: const Size(double.infinity, 52),
                                foregroundColor: Colors.white,
                                side: BorderSide(
                                  color: _selectedLabel == candidate.label
                                      ? const Color(0xFFB9FFDA)
                                      : Colors.white38,
                                  width: 2,
                                ),
                              ),
                              onPressed: _selectedLabel == null
                                  ? () => _selectCandidate(candidate)
                                  : null,
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      SignPhraseComposer.displayLabel(
                                        candidate.label,
                                      ),
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                  Text(
                                    '${(candidate.confidence * 100).round()}%',
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                    ],
                    const SizedBox(height: 10),
                    if (_submitting)
                      const SizedBox(
                        height: 56,
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (_capturing)
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              style: OutlinedButton.styleFrom(
                                minimumSize: const Size(48, 56),
                                foregroundColor: Colors.white,
                              ),
                              onPressed: _cancelCapture,
                              child: const Text('Cancelar'),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            flex: 2,
                            child: FilledButton.icon(
                              style: FilledButton.styleFrom(
                                minimumSize: const Size(48, 56),
                                backgroundColor: const Color(0xFFE33855),
                              ),
                              onPressed: _finishCapture,
                              icon: const Icon(Icons.stop_rounded),
                              label: const Text('Finalizar sinal'),
                            ),
                          ),
                        ],
                      )
                    else
                      FilledButton.icon(
                        style: FilledButton.styleFrom(
                          minimumSize: const Size(double.infinity, 58),
                          backgroundColor: const Color(0xFF7158A0),
                        ),
                        onPressed: _startCapture,
                        icon: const Icon(Icons.fiber_manual_record),
                        label: Text(
                          _candidates.isEmpty
                              ? 'Começar captura'
                              : 'Capturar próximo sinal',
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String get _instruction {
    if (_submitting) return 'Analisando o movimento completo…';
    if (_capturing) {
      return 'Faça um único sinal do começo ao fim e toque em finalizar.';
    }
    if (_candidates.isNotEmpty) {
      return 'Toque na opção correta para ouvir. Se nenhuma servir, grave novamente.';
    }
    return 'Piloto de atendimento de energia: enquadre as mãos e grave uma expressão por vez.';
  }

  Widget _statusPill(String text, Color color) {
    return Container(
      constraints: const BoxConstraints(minHeight: 48),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.circle, color: Colors.white, size: 11),
          const SizedBox(width: 7),
          Text(
            text,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}
