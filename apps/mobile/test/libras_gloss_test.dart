import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/entities/libras_gloss.dart';

void main() {
  group('LibrasGloss', () {
    test('normalizes casing and repeated whitespace', () {
      expect(LibrasGloss('  bom   dia  ').value, 'BOM DIA');
    });

    test('preserves dictionary separators and builds a sequence', () {
      final gloss = LibrasGloss.fromLabels(['bom', 'boa_tarde']);

      expect(gloss.value, 'BOM BOA_TARDE');
      expect(gloss.displayLabel, 'BOM BOA TARDE');
    });
  });
}
