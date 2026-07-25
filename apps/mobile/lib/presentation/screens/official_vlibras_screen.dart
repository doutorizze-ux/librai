import 'package:flutter/material.dart';

import '../../platform/vlibras_avatar_bridge.dart';

class OfficialVlibrasScreen extends StatefulWidget {
  const OfficialVlibrasScreen({
    required this.label,
    super.key,
  });

  final String label;

  @override
  State<OfficialVlibrasScreen> createState() => _OfficialVlibrasScreenState();
}

class _OfficialVlibrasScreenState extends State<OfficialVlibrasScreen> {
  String get _displayName => widget.label.replaceAll('_', ' ');

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      setOfficialVlibrasStageVisible(true);
      playOfficialVlibrasSign(widget.label);
    });
  }

  @override
  void dispose() {
    setOfficialVlibrasStageVisible(false);
    super.dispose();
  }

  void _repeat() {
    playOfficialVlibrasSign(widget.label);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Repetindo $_displayName'),
        duration: const Duration(seconds: 1),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(_displayName),
        centerTitle: true,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
          child: Column(
            children: [
              Text(
                'Demonstração em Libras',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Avatar oficial VLibras',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const Expanded(child: SizedBox()),
              Semantics(
                button: true,
                label: 'Repetir o sinal $_displayName',
                child: FilledButton.icon(
                  onPressed: _repeat,
                  icon: const Icon(Icons.replay),
                  label: const Text('Repetir sinal'),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(56),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Na primeira utilização, pule a apresentação do VLibras.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
