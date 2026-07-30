import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

class VlibrasAvatarView extends StatefulWidget {
  const VlibrasAvatarView({
    required this.gloss,
    this.fallback,
    super.key,
  });

  final String gloss;
  final Widget? fallback;

  @override
  State<VlibrasAvatarView> createState() => _VlibrasAvatarViewState();
}

class _VlibrasAvatarViewState extends State<VlibrasAvatarView> {
  late final String _viewType;
  late final web.HTMLIFrameElement _iframe;

  @override
  void initState() {
    super.initState();
    _viewType = 'librai-vlibras-avatar-${identityHashCode(this)}';
    _iframe = web.HTMLIFrameElement()
      ..title = 'Avatar Librai demonstrando ${widget.gloss}'
      ..style.border = '0'
      ..style.width = '100%'
      ..style.height = '100%'
      ..setAttribute('allowfullscreen', 'true');
    _loadGloss();
    ui_web.platformViewRegistry.registerViewFactory(
      _viewType,
      (_) => _iframe,
    );
  }

  @override
  void didUpdateWidget(covariant VlibrasAvatarView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.gloss != widget.gloss) {
      _loadGloss();
    }
  }

  void _loadGloss() {
    final playerUri = Uri.base.resolve('vlibras-player/').replace(
      queryParameters: {'glosa': widget.gloss},
    );
    _iframe
      ..title = 'Avatar Librai demonstrando ${widget.gloss}'
      ..src = playerUri.toString();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Avatar demonstrando ${widget.gloss} em Libras',
      child: HtmlElementView(viewType: _viewType),
    );
  }
}
