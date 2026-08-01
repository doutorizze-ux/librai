import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/data/quality_training_batch_payload.dart';
import 'package:sinaliza_ai/domain/isolated_sign_label.dart';

void main() {
  test('aceita palavra isolada e rejeita expressão pronta', () {
    expect(IsolatedSignLabel.isValid('obrigado'), isTrue);
    expect(IsolatedSignLabel.isValid('e-mail'), isTrue);
    expect(IsolatedSignLabel.isValid('bom dia'), isFalse);
    expect(IsolatedSignLabel.isValid('oi, tudo bem?'), isFalse);
  });

  test('monta lote v3 aceito pelo tradutor temporal', () {
    final repetitions = List.generate(
      5,
      (repetition) => [
        {
          'timestamp_ms': repetition * 1000,
          'hands': <Map<String, dynamic>>[],
        }
      ],
    );
    final payload = QualityTrainingBatchPayload.build(
      signName: ' ajuda ',
      repetitions: repetitions,
      platform: 'android',
    );

    expect(payload['sign_name'], 'AJUDA');
    expect(payload['format_version'], 3);
    expect(payload['capture_context'], {
      'platform': 'android',
      'camera_facing': 'front',
    });
    expect((payload['repetitions'] as List), hasLength(5));
  });
}
