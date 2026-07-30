import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/libras_gloss.dart';
import '../../platform/vlibras/vlibras_avatar_view.dart';
import '../state/reference_catalog_providers.dart';

class ReferenceSequenceScreen extends ConsumerWidget {
  const ReferenceSequenceScreen({
    required this.text,
    super.key,
  });

  final String text;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sequence = ref.watch(referenceSequenceProvider(text));
    return Scaffold(
      appBar: AppBar(title: const Text('Resposta em Libras')),
      body: sequence.when(
        loading: () => const Center(
          child: CircularProgressIndicator(
            semanticsLabel: 'Preparando resposta em Libras',
          ),
        ),
        error: (error, stackTrace) => const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'Não foi possível preparar a resposta em Libras.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
        data: (data) {
          if (data.signs.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Nenhum sinal disponível para esta mensagem.',
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }

          final gloss = LibrasGloss.fromLabels(
            data.signs.map((sign) => sign.label),
          );
          return SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                  child: Text(
                    data.sourceText,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Expanded(
                  child: VlibrasAvatarView(gloss: gloss.value),
                ),
                if (data.unresolved.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                    child: Text(
                      'Ainda sem referência: ${data.unresolved.join(', ')}',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
