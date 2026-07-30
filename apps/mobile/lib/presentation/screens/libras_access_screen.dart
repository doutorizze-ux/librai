import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/reference_sign.dart';
import '../../platform/device_speech_recognizer.dart';
import '../../platform/vlibras/vlibras_avatar_view.dart';
import '../state/reference_catalog_providers.dart';
import 'reference_motion_screen.dart';

class LibrasAccessScreen extends ConsumerStatefulWidget {
  const LibrasAccessScreen({super.key});

  @override
  ConsumerState<LibrasAccessScreen> createState() =>
      _LibrasAccessScreenState();
}

class _LibrasAccessScreenState extends ConsumerState<LibrasAccessScreen> {
  final _textController = TextEditingController();
  final _speechRecognizer = DeviceSpeechRecognizer();

  bool _speechAvailable = false;
  bool _isListening = false;
  bool _isTranslating = false;
  String? _gloss;
  String? _translatedSource;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_initializeSpeech());
  }

  Future<void> _initializeSpeech() async {
    try {
      final available = await _speechRecognizer.initialize();
      if (mounted) setState(() => _speechAvailable = available);
    } catch (_) {
      if (mounted) setState(() => _speechAvailable = false);
    }
  }

  Future<void> _toggleListening() async {
    if (!_speechAvailable) return;
    if (_speechRecognizer.isListening) {
      await _speechRecognizer.stop();
      if (mounted) setState(() => _isListening = false);
      return;
    }

    setState(() {
      _isListening = true;
      _error = null;
    });
    try {
      await _speechRecognizer.start((text) {
        if (!mounted) return;
        setState(() {
          _textController.value = TextEditingValue(
            text: text,
            selection: TextSelection.collapsed(offset: text.length),
          );
        });
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isListening = false;
        _error =
            'Não foi possível ouvir agora. Verifique a permissão do microfone.';
      });
    }
  }

  Future<void> _translate() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isTranslating) return;

    if (_speechRecognizer.isListening) {
      await _speechRecognizer.stop();
    }
    setState(() {
      _isListening = false;
      _isTranslating = true;
      _error = null;
    });

    try {
      final translation = await ref
          .read(referenceSignRepositoryProvider)
          .translatePortuguese(text);
      if (!mounted) return;
      setState(() {
        _gloss = translation.gloss;
        _translatedSource = translation.sourceText;
        _isTranslating = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isTranslating = false;
        _error =
            'A tradução oficial está indisponível agora. Tente novamente em instantes.';
      });
    }
  }

  @override
  void dispose() {
    unawaited(_speechRecognizer.stop());
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Português para Libras'),
          bottom: const TabBar(
            tabs: [
              Tab(
                icon: Icon(Icons.record_voice_over_rounded),
                text: 'Texto e voz',
              ),
              Tab(
                icon: Icon(Icons.sign_language_rounded),
                text: 'Dicionário',
              ),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _buildTranslator(context),
            const _LibrasDictionaryTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildTranslator(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: _textController,
                  minLines: 2,
                  maxLines: 4,
                  maxLength: 500,
                  textCapitalization: TextCapitalization.sentences,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _translate(),
                  decoration: InputDecoration(
                    labelText: 'Digite ou fale em português',
                    hintText: 'Ex.: Bom dia, como posso ajudar?',
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.translate_rounded),
                    suffixIcon: Semantics(
                      button: true,
                      label: _isListening
                          ? 'Parar de ouvir'
                          : 'Falar uma mensagem em português',
                      child: IconButton(
                        tooltip: _speechAvailable
                            ? (_isListening ? 'Parar' : 'Usar microfone')
                            : 'Microfone indisponível',
                        onPressed:
                            _speechAvailable ? _toggleListening : null,
                        icon: Icon(
                          _isListening ? Icons.stop_rounded : Icons.mic_rounded,
                          color: _isListening
                              ? theme.colorScheme.error
                              : null,
                        ),
                      ),
                    ),
                  ),
                ),
                if (_isListening)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Semantics(
                      liveRegion: true,
                      child: const Row(
                        children: [
                          Icon(Icons.graphic_eq_rounded, color: Colors.red),
                          SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Ouvindo… toque no botão vermelho para parar.',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                Semantics(
                  button: true,
                  label: 'Traduzir mensagem do português para Libras',
                  child: FilledButton.icon(
                    onPressed: _isTranslating ? null : _translate,
                    icon: _isTranslating
                        ? const SizedBox.square(
                            dimension: 22,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.play_arrow_rounded),
                    label: Text(
                      _isTranslating
                          ? 'Traduzindo oficialmente…'
                          : 'Traduzir para Libras',
                    ),
                  ),
                ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Semantics(
                      liveRegion: true,
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: theme.colorScheme.error,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: _gloss == null
                ? const _TranslatorEmptyState()
                : Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(18, 4, 18, 8),
                        child: Semantics(
                          liveRegion: true,
                          label:
                              'Tradução preparada para $_translatedSource',
                          child: Text(
                            'Tradução oficial preparada',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(24),
                          ),
                          child: VlibrasAvatarView(
                            key: ValueKey(_gloss),
                            gloss: _gloss!,
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _TranslatorEmptyState extends StatelessWidget {
  const _TranslatorEmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.accessibility_new_rounded,
              size: 76,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 18),
            Text(
              'A mensagem aparecerá aqui com o avatar Librai.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 10),
            const Text(
              'O Librai não armazena o áudio. A transcrição ou o texto digitado é enviada ao serviço oficial VLibras para preparar os sinais.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _LibrasDictionaryTab extends ConsumerStatefulWidget {
  const _LibrasDictionaryTab();

  @override
  ConsumerState<_LibrasDictionaryTab> createState() =>
      _LibrasDictionaryTabState();
}

class _LibrasDictionaryTabState extends ConsumerState<_LibrasDictionaryTab> {
  final _searchController = TextEditingController();
  Timer? _debounce;
  List<ReferenceSign> _results = const [];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_search(''));
  }

  void _onSearchChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: 350),
      () => _search(value),
    );
  }

  Future<void> _search(String query) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await ref.read(referenceSignRepositoryProvider).search(
            query: query.trim(),
            limit: 100,
          );
      if (!mounted) return;
      setState(() {
        _results = results;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Não foi possível consultar o dicionário agora.';
      });
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: _searchController,
                  onChanged: _onSearchChanged,
                  textInputAction: TextInputAction.search,
                  decoration: InputDecoration(
                    labelText: 'Pesquisar sinal',
                    hintText: 'Ex.: nome, ajuda, prefeitura',
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.search_rounded),
                    suffixIcon: _searchController.text.isEmpty
                        ? null
                        : IconButton(
                            tooltip: 'Limpar pesquisa',
                            onPressed: () {
                              _searchController.clear();
                              setState(() {});
                              _search('');
                            },
                            icon: const Icon(Icons.clear_rounded),
                          ),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '13.597 sinais disponíveis • até 100 resultados por pesquisa',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(20),
              child: Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  style: TextStyle(color: theme.colorScheme.error),
                ),
              ),
            )
          else
            Expanded(
              child: _results.isEmpty && !_loading
                  ? const Center(
                      child: Text('Nenhum sinal encontrado.'),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
                      itemCount: _results.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, index) {
                        final sign = _results[index];
                        final label = sign.label.replaceAll('_', ' ');
                        return Semantics(
                          button: true,
                          label: 'Demonstrar o sinal $label',
                          child: ListTile(
                            minTileHeight: 58,
                            leading:
                                const Icon(Icons.sign_language_rounded),
                            title: Text(
                              label,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w700),
                            ),
                            subtitle: Text(
                              sign.isCompound
                                  ? 'Expressão composta'
                                  : 'Sinal individual',
                            ),
                            trailing:
                                const Icon(Icons.chevron_right_rounded),
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => ReferenceMotionScreen(
                                  label: sign.label,
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
            ),
        ],
      ),
    );
  }
}
