import 'dart:async';
import 'dart:convert';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

class VlibrasAvatarView extends StatefulWidget {
  const VlibrasAvatarView({
    required this.gloss,
    this.avatar = 'hozana',
    this.embedded = false,
    this.fallback,
    super.key,
  });

  final String gloss;
  final String avatar;
  final bool embedded;
  final Widget? fallback;

  @override
  State<VlibrasAvatarView> createState() => _VlibrasAvatarViewState();
}

class _VlibrasAvatarViewState extends State<VlibrasAvatarView> {
  late final String _viewType;
  late final web.HTMLIFrameElement _iframe;
  StreamSubscription<web.Event>? _loadSubscription;

  @override
  void initState() {
    super.initState();
    _viewType = 'librai-vlibras-avatar-${identityHashCode(this)}';
    final prewarmed = web.document.querySelector('#librai-avatar-prewarm');
    if (prewarmed != null) {
      _iframe = prewarmed as web.HTMLIFrameElement;
      _iframe.removeAttribute('id');
      _configureIFrame();
      Timer.run(_sendPlayerState);
    } else {
      _iframe = web.HTMLIFrameElement();
      _configureIFrame();
      _loadInitialPlayer();
    }
    _loadSubscription = _iframe.onLoad.listen((_) => _sendPlayerState());
    ui_web.platformViewRegistry.registerViewFactory(
      _viewType,
      (_) => _iframe,
    );
  }

  void _configureIFrame() {
    _iframe
      ..title = 'Avatar Librai demonstrando ${widget.gloss}'
      ..removeAttribute('aria-hidden')
      ..removeAttribute('tabindex')
      ..style.position = 'static'
      ..style.left = 'auto'
      ..style.top = 'auto'
      ..style.border = '0'
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.opacity = '1'
      ..style.pointerEvents = 'auto'
      ..setAttribute('allowfullscreen', 'true');
  }

  @override
  void didUpdateWidget(covariant VlibrasAvatarView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.gloss != widget.gloss || oldWidget.avatar != widget.avatar) {
      _sendPlayerState();
    }
  }

  void _loadInitialPlayer() {
    final playerUri = Uri.base.resolve('vlibras-player/').replace(
      queryParameters: {
        'glosa': widget.gloss,
        'avatar': widget.avatar,
        if (widget.embedded) 'embedded': '1',
      },
    );
    _iframe
      ..title = 'Avatar Librai demonstrando ${widget.gloss}'
      ..src = playerUri.toString();
  }

  void _sendPlayerState() {
    final gloss = widget.gloss.trim();
    final message = jsonEncode({
      'type': 'librai-play',
      'gloss': gloss,
      'avatar': widget.avatar,
    });
    _iframe.contentWindow?.postMessage(
      message.toJS,
      web.window.location.origin.toJS,
    );
  }

  @override
  void dispose() {
    unawaited(_loadSubscription?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Avatar demonstrando ${widget.gloss} em Libras',
      child: HtmlElementView(viewType: _viewType),
    );
  }
}
