import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../platform/app_config.dart';
import '../../platform/tts_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _logoTapCount = 0;
  DateTime? _lastLogoTapTime;

  void _handleLogoTap() {
    final now = DateTime.now();
    if (_lastLogoTapTime == null ||
        now.difference(_lastLogoTapTime!) > const Duration(seconds: 2)) {
      _logoTapCount = 1;
    } else {
      _logoTapCount++;
    }
    _lastLogoTapTime = now;
    if (_logoTapCount >= 5) {
      _logoTapCount = 0;
      context.push('/trainer');
    }
  }

  void _showSettingsDialog() {
    final controller = TextEditingController(text: AppConfig.apiUrl);
    var temporarySpeed = AppConfig.ttsSpeed;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Row(
            children: [
              Icon(Icons.settings),
              SizedBox(width: 8),
              Text('Configurações'),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'URL da API do servidor:',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: controller,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.link),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  'Velocidade da voz: ${temporarySpeed.toStringAsFixed(1)}x',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Slider(
                  value: temporarySpeed,
                  min: 0.5,
                  max: 2,
                  divisions: 15,
                  onChanged: (value) =>
                      setDialogState(() => temporarySpeed = value),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () {
                final url = controller.text.trim();
                if (url.isNotEmpty) AppConfig.apiUrl = url;
                AppConfig.ttsSpeed = temporarySpeed;
                Navigator.pop(dialogContext);
              },
              child: const Text('Salvar'),
            ),
          ],
        ),
      ),
    ).whenComplete(controller.dispose);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: GestureDetector(
          onTap: _handleLogoTap,
          child: Semantics(
            label: 'Librai',
            child: Image.asset(
              'assets/branding/librai-icon.png',
              height: 46,
              fit: BoxFit.contain,
            ),
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            semanticsLabel: 'Abrir configurações',
            icon: const Icon(Icons.settings),
            onPressed: _showSettingsDialog,
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Card(
                color: theme.colorScheme.primaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.wifi, color: theme.colorScheme.primary),
                      const SizedBox(width: 8),
                      const Text('Conexão: Online'),
                    ],
                  ),
                ),
              ),
              const Spacer(),
              Semantics(
                button: true,
                label: 'Traduzir Libras pela câmera',
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 80),
                    backgroundColor: theme.colorScheme.primary,
                    foregroundColor: theme.colorScheme.onPrimary,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  icon: const Icon(Icons.camera_alt, size: 32),
                  label: const Text(
                    'Traduzir Libras',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  onPressed: () {
                    TtsService().unlock();
                    context.push('/translate');
                  },
                ),
              ),
              const Spacer(flex: 2),
            ],
          ),
        ),
      ),
    );
  }
}
