import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/prediction_consensus.dart';

void main() {
  test('confirma somente resultados válidos e realmente consecutivos', () {
    final consensus = PredictionConsensus();

    expect(consensus.accept(label: 'TUDO BEM', confidence: 0.90), isNull);
    expect(
      consensus.accept(label: 'SINAL_DESCONHECIDO', confidence: 0),
      isNull,
    );
    expect(consensus.accept(label: 'TUDO BEM', confidence: 0.90), isNull);
    expect(
      consensus.accept(label: 'TUDO BEM', confidence: 0.90),
      'TUDO BEM',
    );
  });

  test('um rótulo diferente reinicia a contagem', () {
    final consensus = PredictionConsensus();

    expect(consensus.accept(label: 'OLÁ', confidence: 0.90), isNull);
    expect(consensus.accept(label: 'TUDO BEM', confidence: 0.90), isNull);
    expect(consensus.accept(label: 'OLÁ', confidence: 0.90), isNull);
    expect(consensus.accept(label: 'OLÁ', confidence: 0.90), 'OLÁ');
  });

  test('não confirma confiança abaixo do mínimo', () {
    final consensus = PredictionConsensus(minimumConfidence: 0.75);

    expect(consensus.accept(label: 'OLÁ', confidence: 0.74), isNull);
    expect(consensus.accept(label: 'OLÁ', confidence: 0.90), isNull);
  });
}
