import '../entities/reference_sign.dart';
import '../entities/reference_motion.dart';
import '../entities/reference_sequence.dart';
import '../entities/reference_translation.dart';

abstract interface class ReferenceSignRepository {
  Future<List<ReferenceSign>> search({
    String query = '',
    int limit = 100,
  });

  Future<ReferenceMotion> loadMotion(String label);

  Future<ReferenceSequence> compose(String text);

  Future<ReferenceTranslation> translatePortuguese(String text);
}
