import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sinaliza_ai/main.dart';

void main() {
  testWidgets('Testar renderização da tela inicial do SinalizaAiApp', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: SinalizaAiApp(),
      ),
    );
    await tester.pump();

    expect(find.byType(SinalizaAiApp), findsOneWidget);
    expect(find.text('Traduzir Libras'), findsOneWidget);
    expect(find.text('Conversa'), findsNothing);
    expect(find.text('Ver Histórico de Traduções'), findsNothing);
    expect(find.text('Modelo: v1.0 (Local)'), findsNothing);
  });
}
