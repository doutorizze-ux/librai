import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

class VlibrasAvatarView extends StatefulWidget {
  const VlibrasAvatarView({
    required this.gloss,
    this.embedded = false,
    this.fallback,
    super.key,
  });

  final String gloss;
  final bool embedded;
  final Widget? fallback;

  @override
  State<VlibrasAvatarView> createState() => _VlibrasAvatarViewState();
}

class _VlibrasAvatarViewState extends State<VlibrasAvatarView> {
  static const _productionPlayerBaseUrl = String.fromEnvironment(
    'VLIBRAS_PLAYER_BASE_URL',
    defaultValue: 'https://doutorizze-ux.github.io/librai/vlibras-player/',
  );

  WebViewController? _controller;
  int _progress = 0;
  bool _failed = false;
  bool _pageLoaded = false;

  bool get _isSupported =>
      defaultTargetPlatform == TargetPlatform.android ||
      defaultTargetPlatform == TargetPlatform.iOS;

  @override
  void initState() {
    super.initState();
    if (_isSupported) {
      try {
        _controller = WebViewController()
          ..setJavaScriptMode(JavaScriptMode.unrestricted)
          ..setBackgroundColor(const Color(0xFFF9F5FC))
          ..setNavigationDelegate(
            NavigationDelegate(
              onProgress: (progress) {
                if (!mounted) return;
                setState(() => _progress = progress);
              },
              onPageFinished: (_) {
                if (!mounted) return;
                setState(() {
                  _progress = 100;
                  _failed = false;
                  _pageLoaded = true;
                });
                unawaited(_sendGlossToPlayer());
              },
              onWebResourceError: (error) {
                if (error.isForMainFrame != true || !mounted) return;
                setState(() => _failed = true);
              },
            ),
          )
          ..loadRequest(_playerUri(widget.gloss));
      } catch (_) {
        _failed = true;
      }
    }
  }

  @override
  void didUpdateWidget(covariant VlibrasAvatarView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.gloss != widget.gloss) {
      unawaited(_sendGlossToPlayer());
    }
  }

  Future<void> _sendGlossToPlayer() async {
    final controller = _controller;
    final gloss = widget.gloss.trim();
    if (controller == null || !_pageLoaded || gloss.isEmpty) return;
    try {
      await controller.runJavaScript(
        'window.libraiAvatar && '
        'window.libraiAvatar.setGloss(${jsonEncode(gloss)});',
      );
    } catch (_) {
      if (mounted) setState(() => _failed = true);
    }
  }

  Uri _playerUri(String gloss) {
    return Uri.parse(_productionPlayerBaseUrl).replace(
      queryParameters: {
        'glosa': gloss,
        if (widget.embedded) 'embedded': '1',
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (!_isSupported || controller == null || _failed) {
      return widget.fallback ??
          const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Não foi possível carregar o avatar agora. Verifique a conexão e tente novamente.',
                textAlign: TextAlign.center,
              ),
            ),
          );
    }

    return Semantics(
      label: 'Avatar demonstrando ${widget.gloss} em Libras',
      child: Stack(
        fit: StackFit.expand,
        children: [
          WebViewWidget(controller: controller),
          if (_progress < 100)
            ColoredBox(
              color: const Color(0xFFF9F5FC),
              child: Center(
                child: CircularProgressIndicator(
                  value: _progress == 0 ? null : _progress / 100,
                  semanticsLabel: 'Carregando avatar de Libras',
                ),
              ),
            ),
        ],
      ),
    );
  }
}
