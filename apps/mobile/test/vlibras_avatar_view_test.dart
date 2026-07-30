import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/platform/vlibras/vlibras_avatar_view.dart';

void main() {
  testWidgets('shows a safe fallback on unsupported desktop platforms', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: VlibrasAvatarView(gloss: 'BOM'),
        ),
      ),
    );

    expect(
      find.textContaining('avatar'),
      findsOneWidget,
    );
  });
}
