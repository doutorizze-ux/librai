import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:permission_handler/permission_handler.dart';

const _libraiUrl = 'https://doutorizze-ux.github.io/librai/';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Permission.camera.request();
  runApp(const LibraiAndroidApp());
}

class LibraiAndroidApp extends StatelessWidget {
  const LibraiAndroidApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Librai',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4F378B),
        ),
      ),
      home: const LibraiWebContainer(),
    );
  }
}

class LibraiWebContainer extends StatefulWidget {
  const LibraiWebContainer({super.key});

  @override
  State<LibraiWebContainer> createState() => _LibraiWebContainerState();
}

class _LibraiWebContainerState extends State<LibraiWebContainer> {
  InAppWebViewController? _controller;
  int _progress = 0;
  String? _loadError;

  Future<bool> _handleBack() async {
    final controller = _controller;
    if (controller != null && await controller.canGoBack()) {
      await controller.goBack();
      return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;
        if (await _handleBack() && mounted) {
          await SystemNavigator.pop();
        }
      },
      child: Scaffold(
        body: SafeArea(
          child: Stack(
            children: [
              Semantics(
                label: 'Aplicativo Librai',
                child: InAppWebView(
                  initialUrlRequest: URLRequest(url: WebUri(_libraiUrl)),
                  initialSettings: InAppWebViewSettings(
                    javaScriptEnabled: true,
                    mediaPlaybackRequiresUserGesture: false,
                    allowsInlineMediaPlayback: true,
                    transparentBackground: false,
                  ),
                  onWebViewCreated: (controller) {
                    _controller = controller;
                  },
                  onProgressChanged: (controller, progress) {
                    if (mounted) setState(() => _progress = progress);
                  },
                  onPermissionRequest: (controller, request) async {
                    final status = await Permission.camera.request();
                    return PermissionResponse(
                      resources: request.resources,
                      action: status.isGranted
                          ? PermissionResponseAction.GRANT
                          : PermissionResponseAction.DENY,
                    );
                  },
                  onReceivedError: (controller, request, error) {
                    if (request.isForMainFrame == true && mounted) {
                      setState(() => _loadError = error.description);
                    }
                  },
                  onLoadStop: (controller, url) {
                    if (mounted) setState(() => _loadError = null);
                  },
                ),
              ),
              if (_progress < 100 && _loadError == null)
                const Center(child: CircularProgressIndicator()),
              if (_loadError != null)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.cloud_off, size: 52),
                        const SizedBox(height: 16),
                        const Text(
                          'Não foi possível abrir o Librai.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Confira a conexão com a internet e tente novamente.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 20),
                        FilledButton.icon(
                          onPressed: () {
                            setState(() => _loadError = null);
                            _controller?.loadUrl(
                              urlRequest: URLRequest(url: WebUri(_libraiUrl)),
                            );
                          },
                          icon: const Icon(Icons.refresh),
                          label: const Text('Tentar novamente'),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
