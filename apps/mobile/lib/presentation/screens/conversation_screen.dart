import 'dart:math';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../data/datasources/local_history_storage.dart';
import '../../platform/tts_service.dart';
import '../../platform/local_translator.dart';
import '../state/glosses_buffer.dart';

class ConversationScreen extends StatefulWidget {
  const ConversationScreen({super.key});

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen> {
  final TtsService _ttsService = TtsService();
  final LocalLibrasTranslator _translator = LocalLibrasTranslator();
  final LocalHistoryStorage _historyStorage = LocalHistoryStorage();
  final GlossesBuffer _glossesBuffer = GlossesBuffer();

  final List<String> _chatTranscript = [];
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  
  final String _sessionId = "session_${DateTime.now().millisecondsSinceEpoch}";
  bool _isCameraActive = true;

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // Ouvinte envia uma mensagem de texto (que pode ser reproduzida via TTS)
  void _sendHearingMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    setState(() {
      _chatTranscript.add("Ouvinte: $text");
      _textController.clear();
    });
    _scrollToBottom();
  }

  // Simula a detecção de um sinal de Libras pela câmera do surdo
  Future<void> _simulateDeafSign(String gloss) async {
    // Adiciona ao buffer de glosses com deduplicação
    _glossesBuffer.addGloss(gloss);

    // Traduz a sequência acumulada de glosses
    final translation = await _translator.translate(_glossesBuffer.glosses, sessionId: _sessionId);

    setState(() {
      // Atualiza o último balão do surdo se a frase estiver evoluindo, ou cria um novo
      if (_chatTranscript.isNotEmpty && _chatTranscript.last.startsWith("Surdo:")) {
        _chatTranscript.removeLast();
      }
      _chatTranscript.add("Surdo: $translation");
    });
    
    _scrollToBottom();
  }

  // Finaliza a frase de Libras (limpa o buffer para o próximo ciclo)
  void _finalizeDeafSentence() {
    // Fala o resultado da tradução por voz (TTS) para acessibilidade do ouvinte
    if (_chatTranscript.isNotEmpty && _chatTranscript.last.startsWith("Surdo:")) {
      final text = _chatTranscript.last.replaceFirst("Surdo: ", "");
      _ttsService.speak(text);
    }
    _glossesBuffer.clear();
  }

  // Salva a sessão no histórico e volta
  void _saveAndExit() {
    if (_chatTranscript.isNotEmpty) {
      final session = TranslationSession(
        id: _sessionId,
        timestamp: DateTime.now(),
        transcript: List.from(_chatTranscript),
      );
      _historyStorage.saveSession(session);
    }
    context.pop();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Modo Conversa'),
        actions: [
          IconButton(
            icon: Semantics(
              label: 'Exportar histórico da sessão',
              child: const Icon(Icons.share),
            ),
            onPressed: () {
              // Exportação LGPD formatada
              final json = _historyStorage.exportSessionsAsJson();
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Sessão exportada (${json.length} bytes)')),
              );
            },
          ),
          IconButton(
            icon: Semantics(
              label: 'Salvar e sair da sessão',
              child: const Icon(Icons.check_circle_outline),
            ),
            onPressed: _saveAndExit,
          ),
        ],
      ),
      body: Column(
        children: [
          // Divisão Superior: Visão da Câmera do Surdo (Reduzido para chat)
          if (_isCameraActive)
            Container(
              height: 180,
              margin: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black87,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: theme.colorScheme.primary, width: 2),
              ),
              child: Stack(
                children: [
                  Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.videocam, color: theme.colorScheme.primary.withOpacity(0.4), size: 48),
                        const Text(
                          'Câmera Ativa - Sinalize abaixo',
                          style: TextStyle(color: Colors.white70, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  Positioned(
                    bottom: 8,
                    left: 8,
                    right: 8,
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          _buildSimulateButton('BOM_DIA'),
                          const SizedBox(width: 8),
                          _buildSimulateButton('AJUDA'),
                          const SizedBox(width: 8),
                          _buildSimulateButton('SAÚDE'),
                          const SizedBox(width: 8),
                          _buildSimulateButton('EMERGÊNCIA'),
                          const SizedBox(width: 8),
                          _buildSimulateButton('EU'),
                          const SizedBox(width: 8),
                          _buildSimulateButton('IR'),
                          const SizedBox(width: 8),
                          _buildSimulateButton('HOSPITAL'),
                          const SizedBox(width: 8),
                          ElevatedButton(
                            style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
                            onPressed: _finalizeDeafSentence,
                            child: const Text('Falar Frase (TTS)'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          
          // Divisão Central: Histórico de Conversa / Balões
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _chatTranscript.length,
              itemBuilder: (context, index) {
                final line = _chatTranscript[index];
                final isDeaf = line.startsWith("Surdo:");
                final text = isDeaf ? line.replaceFirst("Surdo: ", "") : line.replaceFirst("Ouvinte: ", "");

                return Align(
                  alignment: isDeaf ? Alignment.centerLeft : Alignment.centerRight,
                  child: Container(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.75,
                    ),
                    margin: const EdgeInsets.symmetric(vertical: 6),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: isDeaf 
                        ? theme.colorScheme.primaryContainer 
                        : theme.colorScheme.secondaryContainer,
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(16),
                        topRight: const Radius.circular(16),
                        bottomLeft: isDeaf ? Radius.zero : const Radius.circular(16),
                        bottomRight: isDeaf ? const Radius.circular(16) : Radius.zero,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isDeaf ? "Surdo (Libras)" : "Ouvinte (Português)",
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          text,
                          style: theme.textTheme.bodyMedium,
                        ),
                        if (isDeaf) ...[
                          const SizedBox(height: 4),
                          Align(
                            alignment: Alignment.bottomRight,
                            child: IconButton(
                              icon: Semantics(
                                label: 'Ouvir tradução em voz',
                                child: const Icon(Icons.volume_up, size: 18),
                              ),
                              onPressed: () => _ttsService.speak(text),
                            ),
                          ),
                        ]
                      ],
                    ),
                  ),
                );
              },
            ),
          ),

          // Divisão Inferior: Entrada do Ouvinte
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    decoration: InputDecoration(
                      hintText: 'Escreva uma mensagem para o surdo...',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                    ),
                    onSubmitted: (_) => _sendHearingMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                FloatingActionButton(
                  onPressed: _sendHearingMessage,
                  tooltip: 'Enviar mensagem para conversação',
                  child: const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSimulateButton(String label) {
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: Colors.blueGrey,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),
      onPressed: () => _simulateDeafSign(label),
      child: Text(label),
    );
  }
}
