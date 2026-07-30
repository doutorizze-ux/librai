import 'package:flutter/material.dart';

class VlibrasAvatarView extends StatelessWidget {
  const VlibrasAvatarView({
    required this.gloss,
    this.fallback,
    super.key,
  });

  final String gloss;
  final Widget? fallback;

  @override
  Widget build(BuildContext context) {
    return fallback ??
        const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'O avatar de Libras está disponível no aplicativo e na versão web.',
              textAlign: TextAlign.center,
            ),
          ),
        );
  }
}
