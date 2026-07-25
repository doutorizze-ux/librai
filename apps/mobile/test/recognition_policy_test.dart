import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/recognition_policy.dart';

void main() {
  group('RecognitionPolicy', () {
    test('blocks isolated alphabet poses in normal translation mode', () {
      expect(
        RecognitionPolicy.isUnsupportedStaticAlphabetPrediction('D'),
        isTrue,
      );
      expect(
        RecognitionPolicy.isUnsupportedStaticAlphabetPrediction(' a '),
        isTrue,
      );
    });

    test('does not block complete signs', () {
      expect(
        RecognitionPolicy.isUnsupportedStaticAlphabetPrediction('DIA'),
        isFalse,
      );
      expect(
        RecognitionPolicy.isUnsupportedStaticAlphabetPrediction('TARDE'),
        isFalse,
      );
    });
  });
}
