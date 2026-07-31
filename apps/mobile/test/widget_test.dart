import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sinaliza_ai/main.dart';
import 'package:sinaliza_ai/presentation/screens/translation_screen.dart';

void main() {
  testWidgets('Testar renderização da tela inicial do SinalizaAiApp',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: SinalizaAiApp(),
      ),
    );
    await tester.pump();

    expect(find.byType(SinalizaAiApp), findsOneWidget);
  });

  testWidgets('abre o tradutor automático ligado aos treinamentos', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const ProviderScope(child: SinalizaAiApp()),
    );

    await tester.tap(find.text('Traduzir Libras'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.byType(TranslationScreen), findsOneWidget);
    expect(find.text('Começar captura'), findsNothing);

    await tester.pumpWidget(const SizedBox.shrink());
  });
}
