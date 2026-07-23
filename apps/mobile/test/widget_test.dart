import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sinaliza_ai/main.dart';

void main() {
  testWidgets('Testar renderização da tela inicial e botões principais', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: SinalizaAiApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(SinalizaAiApp), findsOneWidget);
    expect(find.text('Traduzir Libras'), findsAtLeast(1));
    expect(find.text('Conversa'), findsAtLeast(1));
    expect(find.text('Aprender'), findsAtLeast(1));
  });
}
