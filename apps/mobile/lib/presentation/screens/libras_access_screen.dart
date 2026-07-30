import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/reference_sign.dart';
import '../../platform/device_speech_recognizer.dart';
import '../../platform/vlibras/vlibras_avatar_view.dart';
import '../state/reference_catalog_providers.dart';

class LibrasAccessScreen extends ConsumerStatefulWidget {
  const LibrasAccessScreen({super.key});

  @override
  ConsumerState<LibrasAccessScreen> createState() => _LibrasAccessScreenState();
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
                        onPressed: _speechAvailable ? _toggleListening : null,
                        icon: Icon(
                          _isListening ? Icons.stop_rounded : Icons.mic_rounded,
                          color: _isListening ? theme.colorScheme.error : null,
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
          if (_gloss != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 4, 18, 8),
              child: Semantics(
                liveRegion: true,
                label: 'Tradução preparada para $_translatedSource',
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
              child: Stack(
                fit: StackFit.expand,
                children: [
                  // O player é carregado enquanto a pessoa digita. Quando a
                  // tradução chega, a mesma instância recebe a nova sequência.
                  VlibrasAvatarView(gloss: _gloss ?? ''),
                  if (_gloss == null)
                    const ColoredBox(
                      color: Color(0xFFF9F5FC),
                      child: _TranslatorEmptyState(),
                    ),
                ],
              ),
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
  static const _pageSize = 100;

  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _debounce;
  List<ReferenceSign> _results = const [];
  bool _loading = false;
  bool _loadingMore = false;
  bool _hasMore = true;
  String? _error;
  String? _selectedGloss;
  int _searchGeneration = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    unawaited(_search(''));
  }

  void _onScroll() {
    if (_scrollController.position.extentAfter < 500) {
      unawaited(_loadMore());
    }
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
    final generation = ++_searchGeneration;
    setState(() {
      _loading = true;
      _loadingMore = false;
      _hasMore = true;
      _error = null;
    });
    try {
      final results = await ref.read(referenceSignRepositoryProvider).search(
            query: query.trim(),
            offset: 0,
            limit: _pageSize,
          );
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        _results = results;
        _loading = false;
        _hasMore = results.length == _pageSize;
      });
    } catch (_) {
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        _loading = false;
        _error = 'Não foi possível consultar o dicionário agora.';
      });
    }
  }

  Future<void> _loadMore() async {
    if (_loading || _loadingMore || !_hasMore || _error != null) return;
    final generation = _searchGeneration;
    setState(() => _loadingMore = true);
    try {
      final results = await ref.read(referenceSignRepositoryProvider).search(
            query: _searchController.text.trim(),
            offset: _results.length,
            limit: _pageSize,
          );
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        _results = [..._results, ...results];
        _loadingMore = false;
        _hasMore = results.length == _pageSize;
      });
    } catch (_) {
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        _loadingMore = false;
        _error = 'Não foi possível carregar mais sinais agora.';
      });
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _scrollController.dispose();
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
                  'Mais de 22 mil sinais oficiais • pesquise pelo nome',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
          if (_selectedGloss != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
              child: SizedBox(
                height: 360,
                child: Material(
                  color: theme.colorScheme.surface,
                  clipBehavior: Clip.antiAlias,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(22),
                    side: BorderSide(
                      color: theme.colorScheme.outlineVariant,
                    ),
                  ),
                  child: Column(
                    children: [
                      SizedBox(
                        height: 64,
                        child: Padding(
                          padding: const EdgeInsets.only(left: 16, right: 8),
                          child: Row(
                            children: [
                              Icon(
                                Icons.sign_language_rounded,
                                color: theme.colorScheme.primary,
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  _selectedGloss!.replaceAll('_', ' '),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                              Semantics(
                                button: true,
                                label: 'Fechar demonstração do sinal',
                                child: IconButton.filledTonal(
                                  constraints: const BoxConstraints.tightFor(
                                    width: 48,
                                    height: 48,
                                  ),
                                  tooltip: 'Fechar demonstração',
                                  onPressed: () => setState(
                                    () => _selectedGloss = null,
                                  ),
                                  icon: const Icon(Icons.close_rounded),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      Divider(
                        height: 1,
                        color: theme.colorScheme.outlineVariant,
                      ),
                      Expanded(
                        child: VlibrasAvatarView(
                          gloss: _selectedGloss!,
                          embedded: true,
                        ),
                      ),
                    ],
                  ),
                ),
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
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
                      itemCount: _results.length + (_loadingMore ? 1 : 0),
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, index) {
                        if (index == _results.length) {
                          return const Padding(
                            padding: EdgeInsets.all(20),
                            child: Center(
                              child: CircularProgressIndicator(
                                semanticsLabel: 'Carregando mais sinais',
                              ),
                            ),
                          );
                        }
                        final sign = _results[index];
                        final label = sign.label.replaceAll('_', ' ');
                        return Semantics(
                          button: true,
                          label: 'Demonstrar o sinal $label',
                          child: ListTile(
                            minTileHeight: 58,
                            leading: const Icon(Icons.sign_language_rounded),
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
                            trailing: const Icon(Icons.chevron_right_rounded),
                            onTap: () => setState(
                              () => _selectedGloss = sign.label,
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
