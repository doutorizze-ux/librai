import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sinaliza_ai/domain/entities/vlibras_avatar.dart';
import 'package:sinaliza_ai/presentation/screens/home_screen.dart';
import 'package:sinaliza_ai/presentation/state/vlibras_avatar_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('lets the user choose one of the official avatars',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: HomeScreen()),
      ),
    );

    await tester.tap(find.byTooltip('Configurações'));
    await tester.pumpAndSettle();

    expect(find.text('Hozana'), findsOneWidget);
    expect(find.text('Ícaro'), findsOneWidget);

    await tester.tap(find.text('Ícaro'));
    await tester.tap(find.text('Salvar'));
    await tester.pumpAndSettle();

    final container = ProviderScope.containerOf(
      tester.element(find.byType(HomeScreen)),
    );
    expect(container.read(vlibrasAvatarProvider), VlibrasAvatar.icaro);
  });
}
