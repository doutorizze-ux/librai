import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sinaliza_ai/main.dart';

void main() {
  testWidgets('Testar renderização da tela inicial e botões principais', (WidgetTester tester) async {
    // Inicializar o App envolto no ProviderScope do Riverpod
    await tester.pumpWidget(
      const ProviderScope(
        child: SinalizaAiApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    // Verificar se o título principal é renderizado
    expect(find.text('LibrAI'), findsAtLeast(1));

    // Verificar a presença do botão principal de tradução
    expect(find.text('Traduzir Libras'), findsOneWidget);

    // Verificar botões de Conversa e Aprender
    expect(find.text('Conversa'), findsOneWidget);
    expect(find.text('Aprender'), findsOneWidget);
  });
}
