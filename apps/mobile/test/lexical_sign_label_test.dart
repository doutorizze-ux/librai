import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/lexical_sign_label.dart';

void main() {
  test('keeps a multiword Portuguese label as one Libras lexical unit', () {
    expect(LexicalSignLabel.normalize('  Tudo   bem? '), 'TUDO BEM?');
    expect(LexicalSignLabel.isValid('Tudo bem?'), isTrue);
  });

  test('rejects labels that could inject markup or unrelated punctuation', () {
    expect(LexicalSignLabel.isValid('<script>'), isFalse);
    expect(LexicalSignLabel.isValid('OLA, TUDO BEM'), isFalse);
  });
}
