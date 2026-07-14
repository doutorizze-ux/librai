import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final size = MediaQuery.of(context).size;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sinaliza AI'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            semanticsLabel: 'Acesso às configurações',
            onPressed: () {
              // Ações de configurações
            },
          ),
        ],
      ),
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
                  onPressed: () => context.push('/translate'),
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
