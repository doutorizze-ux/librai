import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/entities/reference_motion.dart';
import 'package:sinaliza_ai/domain/entities/reference_sequence.dart';
import 'package:sinaliza_ai/domain/entities/reference_sign.dart';
import 'package:sinaliza_ai/domain/entities/reference_translation.dart';
import 'package:sinaliza_ai/domain/repositories/reference_sign_repository.dart';
import 'package:sinaliza_ai/presentation/screens/libras_access_screen.dart';
import 'package:sinaliza_ai/presentation/state/reference_catalog_providers.dart';

class _FakeReferenceSignRepository implements ReferenceSignRepository {
  @override
  Future<ReferenceSequence> compose(String text) async {
    return ReferenceSequence(
      sourceText: text,
      signs: const [],
      unresolved: const [],
    );
  }

  @override
  Future<ReferenceMotion> loadMotion(String label) {
    throw UnimplementedError();
  }

  @override
  Future<List<ReferenceSign>> search({
    String query = '',
    int offset = 0,
    int limit = 100,
  }) async {
    return const [
      ReferenceSign(
        id: 'ajuda',
        label: 'AJUDA',
        platforms: ['webgl'],
        isCompound: false,
        motionReady: true,
      ),
    ];
  }

  @override
  Future<ReferenceTranslation> translatePortuguese(String text) async {
    return ReferenceTranslation(
      sourceText: text,
      gloss: 'BOM DIA',
    );
  }
}

void main() {
  testWidgets('translates typed Portuguese and exposes the complete dictionary', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          referenceSignRepositoryProvider.overrideWithValue(
            _FakeReferenceSignRepository(),
          ),
        ],
        child: const MaterialApp(home: LibrasAccessScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Texto e voz'), findsOneWidget);
    expect(find.text('Dicionário'), findsOneWidget);

    await tester.enterText(
      find.byType(TextField).first,
      'Bom dia',
    );
    await tester.tap(find.text('Traduzir para Libras'));
    await tester.pumpAndSettle();

    expect(find.text('Tradução oficial preparada'), findsOneWidget);

    await tester.tap(find.text('Dicionário'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Mais de 22 mil sinais'), findsOneWidget);
    expect(find.text('AJUDA'), findsOneWidget);
  });
}
