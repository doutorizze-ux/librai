import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/reference_avatar_asset_catalog.dart';
import '../state/reference_catalog_providers.dart';
import '../widgets/reference_avatar_video_player.dart';
import 'reference_motion_screen.dart';

class ReferenceSequenceScreen extends ConsumerStatefulWidget {
  const ReferenceSequenceScreen({
    required this.text,
    super.key,
  });

  final String text;

  @override
  ConsumerState<ReferenceSequenceScreen> createState() =>
      _ReferenceSequenceScreenState();
}

class _ReferenceSequenceScreenState
    extends ConsumerState<ReferenceSequenceScreen> {
  int _currentIndex = 0;

  void _advance(int count) {
    if (!mounted || count == 0) return;
    setState(() {
      _currentIndex = (_currentIndex + 1) % count;
    });
  }

  @override
  Widget build(BuildContext context) {
    final sequence = ref.watch(referenceSequenceProvider(widget.text));
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
          final index = _currentIndex % data.signs.length;
          final sign = data.signs[index];
          final motion = ref.watch(referenceMotionProvider(sign.label));
          final avatarAsset = ReferenceAvatarAssetCatalog.assetFor(sign.label);
          final motionPlayer = motion.when(
            loading: () => const Center(
              child: CircularProgressIndicator(),
            ),
            error: (error, stackTrace) => Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'O movimento de ${sign.label.replaceAll('_', ' ')} ainda não foi publicado.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: () => _advance(data.signs.length),
                    child: const Text('Próximo sinal'),
                  ),
                ],
              ),
            ),
            data: (referenceMotion) => ReferenceMotionPlayer(
              key: ValueKey('motion-${sign.label}'),
              motion: referenceMotion,
              compact: true,
              loop: false,
              onCompleted: () => _advance(data.signs.length),
            ),
          );
          return SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
                  child: Text(
                    data.sourceText,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 6,
                  children: [
                    for (var position = 0;
                        position < data.signs.length;
                        position++)
                      Chip(
                        avatar: position == index
                            ? const Icon(Icons.play_arrow, size: 18)
                            : null,
                        label: Text(
                          data.signs[position].label.replaceAll('_', ' '),
                        ),
                      ),
                  ],
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: avatarAsset == null
                        ? motionPlayer
                        : ReferenceAvatarVideoPlayer(
                            key: ValueKey('avatar-${sign.label}'),
                            assetPath: avatarAsset,
                            label: sign.label,
                            compact: true,
                            loop: false,
                            onCompleted: () => _advance(data.signs.length),
                            fallback: motionPlayer,
                          ),
                  ),
                ),
                if (data.unresolved.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
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
