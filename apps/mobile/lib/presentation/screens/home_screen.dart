import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../platform/tts_service.dart';
import '../../platform/app_config.dart';

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
    if (_lastLogoTapTime == null || now.difference(_lastLogoTapTime!) > const Duration(seconds: 2)) {
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

  void _showSettingsDialog(BuildContext context) {
    final controller = TextEditingController(text: AppConfig.apiUrl);
    double tempSpeed = AppConfig.ttsSpeed;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Row(
                children: [
                  Icon(Icons.settings),
                  SizedBox(width: 8),
                  Text("Configurações"),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      "URL da API do Servidor (Coolify):",
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: controller,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        hintText: "https://api.tvcatolica.site",
                        prefixIcon: Icon(Icons.link),
                      ),
                    ),
                    const SizedBox(height: 20),
                    Text(
                      "Velocidade da Voz (TTS): ${tempSpeed.toStringAsFixed(1)}x",
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    Slider(
                      value: tempSpeed,
                      min: 0.5,
                      max: 2.0,
                      divisions: 15,
                      label: "${tempSpeed.toStringAsFixed(1)}x",
                      onChanged: (val) {
                        setDialogState(() {
                          tempSpeed = val;
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text("Cancelar"),
                ),
                ElevatedButton(
                  onPressed: () {
                    final newUrl = controller.text.trim();
                    if (newUrl.isNotEmpty) {
                      AppConfig.apiUrl = newUrl;
                      AppConfig.ttsSpeed = tempSpeed;
                      Navigator.pop(context);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text("Configurações salvas com sucesso!"),
                          backgroundColor: Colors.green,
                        ),
                      );
                    }
                  },
                  child: const Text("Salvar"),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final size = MediaQuery.of(context).size;

    return Scaffold(
      appBar: AppBar(
        title: GestureDetector(
          onTap: _handleLogoTap,
          child: const Text('LibrAI', style: TextStyle(fontWeight: FontWeight.bold)),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: Semantics(
              label: 'Acesso às configurações',
              child: const Icon(Icons.settings),
            ),
            onPressed: () => _showSettingsDialog(context),
          ),
        ],
      );
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Banner de Boas-vindas / Info do App
              Card(
                elevation: 0,
                color: theme.colorScheme.primaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Icon(Icons.wifi, color: theme.colorScheme.primary),
                              const SizedBox(width: 8),
                              const Text('Conexão: Online'),
                            ],
                          ),
                          Row(
                            children: [
                              Icon(Icons.check_circle, color: theme.colorScheme.primary),
                              const SizedBox(width: 8),
                              const Text('Modelo: v1.0 (Local)'),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const Spacer(),
              
              // Botão Principal: Traduzir Libras
              Semantics(
                button: true,
                label: 'Traduzir Libras via Câmera',
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 80),
                    backgroundColor: theme.colorScheme.primary,
                    foregroundColor: theme.colorScheme.onPrimary,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16.0),
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
              const SizedBox(height: 20),
              
              // Grid de Ações Secundárias
              Row(
                children: [
                  Expanded(
                    child: Semantics(
                      button: true,
                      label: 'Modo Conversa em Tela Dividida',
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          minimumSize: const Size(double.infinity, 70),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16.0),
                          ),
                        ),
                        icon: const Icon(Icons.forum),
                        label: const Text('Conversa'),
                        onPressed: () => context.push('/conversation'),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Semantics(
                      button: true,
                      label: 'Aprender Sinais Dicionário',
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          minimumSize: const Size(double.infinity, 70),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16.0),
                          ),
                        ),
                        icon: const Icon(Icons.menu_book),
                        label: const Text('Aprender'),
                        onPressed: () => context.push('/dictionary'),
                      ),
                    ),
                  ),
                ],
              ),
              const Spacer(),
              
              // Histórico e Privacidade
              TextButton.icon(
                icon: const Icon(Icons.history),
                label: const Text('Ver Histórico de Traduções'),
                onPressed: () {
                  // Abre histórico
                },
              ),
              const SizedBox(height: 8),
              Center(
                child: TextButton(
                  child: const Text('Termos & Política de Privacidade (LGPD)'),
                  onPressed: () {
                    // Abre termos de privacidade
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
