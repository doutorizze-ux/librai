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
      backgroundColor: const Color(0xFFFAF8FD),
      appBar: AppBar(
        toolbarHeight: 68,
        title: GestureDetector(
          onTap: _handleLogoTap,
          child: Semantics(
            label: 'Librai',
            child: SizedBox(
              width: 62,
              height: 62,
              child: ClipRect(
                child: Transform.scale(
                  scale: 1.55,
                  child: Image.asset(
                    'assets/branding/librai-icon.png',
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            ),
          ),
        ),
        centerTitle: true,
        actions: [
          Semantics(
            button: true,
            label: 'Abrir configurações',
            child: IconButton(
              tooltip: 'Configurações',
              icon: const Icon(Icons.settings),
              onPressed: _showSettingsDialog,
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 18, 24, 28),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Align(
                      alignment: Alignment.center,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEDE5FA),
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(color: const Color(0xFFDCCEF3)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 9,
                              height: 9,
                              decoration: const BoxDecoration(
                                color: Color(0xFF29A866),
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 8),
                            const Text(
                              'Piloto de atendimento de energia',
                              style: TextStyle(
                                color: Color(0xFF513C78),
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    SizedBox(height: constraints.maxHeight < 650 ? 42 : 72),
                    Center(
                      child: SizedBox(
                        width: constraints.maxWidth < 420 ? 170 : 205,
                        height: constraints.maxWidth < 420 ? 170 : 205,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(48),
                          child: Transform.scale(
                            scale: 1.18,
                            child: Image.asset(
                              'assets/branding/librai-icon.png',
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 28),
                    const Text(
                      'Librai',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xFF251C32),
                        fontSize: 38,
                        height: 1,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -1.2,
                      ),
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      'Libras em movimento.\nComunicação sem barreiras.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xFF655A70),
                        fontSize: 18,
                        height: 1.4,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    SizedBox(height: constraints.maxHeight < 650 ? 42 : 74),
                    Semantics(
                      button: true,
                      label:
                          'Abrir reconhecimento assistido para atendimento de energia',
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          elevation: 0,
                          minimumSize: const Size(double.infinity, 68),
                          backgroundColor: const Color(0xFF6C5598),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(22),
                          ),
                        ),
                        icon: const Icon(Icons.camera_alt_rounded, size: 29),
                        label: const Text(
                          'Testar reconhecimento',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        onPressed: () {
                          TtsService().unlock();
                          context.push('/translate');
                        },
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      '175 expressões de atendimento de energia. Grave um sinal e confirme entre três opções.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: theme.colorScheme.onSurfaceVariant,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
