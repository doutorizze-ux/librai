import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/reference_sign.dart';
import '../state/reference_catalog_providers.dart';
import 'reference_motion_screen.dart';

class DictionaryScreen extends ConsumerStatefulWidget {
  const DictionaryScreen({super.key});

  @override
  ConsumerState<DictionaryScreen> createState() => _DictionaryScreenState();
}

class _DictionaryScreenState extends ConsumerState<DictionaryScreen> {
  Timer? _searchDebounce;
  String _query = '';

  @override
  void dispose() {
    _searchDebounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _query = value.trim());
    });
  }

  @override
  Widget build(BuildContext context) {
    final catalog = ref.watch(referenceCatalogProvider(_query));

    return Scaffold(
      appBar: AppBar(title: const Text('Dicionário de Libras')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Semantics(
              textField: true,
              label: 'Pesquisar no catálogo de sinais de Libras',
              child: TextField(
                onChanged: _onSearchChanged,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  hintText: 'Pesquise entre mais de 13 mil sinais',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ),
          ),
          Expanded(
            child: catalog.when(
              loading: () => const Center(
                child: CircularProgressIndicator(
                  semanticsLabel: 'Carregando catálogo de Libras',
                ),
              ),
              error: (error, stackTrace) => _CatalogError(
                onRetry: () =>
                    ref.invalidate(referenceCatalogProvider(_query)),
              ),
              data: (signs) => signs.isEmpty
                  ? const Center(
                      child: Text('Nenhum sinal encontrado.'),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                      itemCount: signs.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (context, index) =>
                          _ReferenceSignCard(sign: signs[index]),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReferenceSignCard extends StatelessWidget {
  const _ReferenceSignCard({required this.sign});

  final ReferenceSign sign;

  @override
  Widget build(BuildContext context) {
    final displayName = sign.label.replaceAll('_', ' ');
    return Semantics(
      button: true,
      label: sign.isCompound
          ? '$displayName, expressão composta'
          : '$displayName, sinal de Libras',
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          minTileHeight: 64,
          leading: const Icon(Icons.sign_language_outlined),
          title: Text(
            displayName,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          subtitle: Text(
            sign.isCompound ? 'Expressão composta' : 'Sinal individual',
          ),
          trailing: sign.motionReady
              ? const Icon(Icons.chevron_right)
              : const Icon(Icons.hourglass_bottom),
          onTap: sign.motionReady ? () {
            Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => ReferenceMotionScreen(label: sign.label),
              ),
            );
          } : null,
        ),
      ),
    );
  }
}

class _CatalogError extends StatelessWidget {
  const _CatalogError({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 48),
            const SizedBox(height: 12),
            const Text(
              'Não foi possível carregar o catálogo agora.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Tentar novamente'),
              style: FilledButton.styleFrom(
                minimumSize: const Size(48, 48),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
