import '../../domain/entities/reference_sign.dart';
import '../../domain/entities/reference_motion.dart';
import '../../domain/entities/reference_sequence.dart';
import '../../domain/entities/reference_translation.dart';
import '../../domain/repositories/reference_sign_repository.dart';
import '../datasources/vlibras_reference_remote_datasource.dart';

class ReferenceSignRepositoryImpl implements ReferenceSignRepository {
  const ReferenceSignRepositoryImpl(this._datasource);

  final VlibrasReferenceRemoteDatasource _datasource;

  @override
  Future<List<ReferenceSign>> search({
    String query = '',
    int limit = 100,
  }) async {
    final records = await _datasource.search(query: query, limit: limit);
    return records
        .map(
          (record) => ReferenceSign(
            id: record['id'] as String,
            label: record['label'] as String,
            platforms: (record['platforms'] as List)
                .whereType<String>()
                .toList(growable: false),
            isCompound: record['is_compound'] as bool? ?? false,
            motionReady: record['motion_ready'] as bool? ?? false,
          ),
        )
        .toList(growable: false);
  }

  @override
  Future<ReferenceMotion> loadMotion(String label) async {
    final record = await _datasource.loadMotion(label);
    final frames = (record['frames'] as List)
        .whereType<Map>()
        .map((rawFrame) {
          final frame = Map<String, dynamic>.from(rawFrame);
          return ReferenceMotionFrame(
            time: (frame['time'] as num).toDouble(),
            body: _bodyPoints(frame['body']),
            leftHand: _points(frame['left_hand']),
            rightHand: _points(frame['right_hand']),
          );
        })
        .toList(growable: false);
    return ReferenceMotion(
      label: record['label'] as String,
      fps: record['fps'] as int,
      duration: Duration(
        milliseconds:
            ((record['duration_seconds'] as num).toDouble() * 1000).round(),
      ),
      frames: frames,
    );
  }

  @override
  Future<ReferenceSequence> compose(String text) async {
    final record = await _datasource.compose(text);
    return ReferenceSequence(
      sourceText: record['source_text'] as String,
      signs: (record['signs'] as List)
          .whereType<Map>()
          .map(
            (rawSign) => ReferenceSequenceSign(
              label: rawSign['label'] as String,
              motionReady: rawSign['motion_ready'] as bool? ?? false,
            ),
          )
          .toList(growable: false),
      unresolved: (record['unresolved'] as List)
          .whereType<String>()
          .toList(growable: false),
    );
  }

  @override
  Future<ReferenceTranslation> translatePortuguese(String text) async {
    final record = await _datasource.translatePortuguese(text);
    return ReferenceTranslation(
      sourceText: record['source_text'] as String,
      gloss: record['gloss'] as String,
    );
  }

  static Map<String, ReferencePoint> _bodyPoints(Object? rawBody) {
    final body = Map<String, dynamic>.from(rawBody as Map);
    return body.map(
      (name, value) => MapEntry(name, _point(value)),
    );
  }

  static List<ReferencePoint> _points(Object? rawPoints) {
    return (rawPoints as List)
        .map(_point)
        .toList(growable: false);
  }

  static ReferencePoint _point(Object? rawPoint) {
    final coordinates = rawPoint as List;
    return ReferencePoint(
      (coordinates[0] as num).toDouble(),
      (coordinates[1] as num).toDouble(),
      (coordinates[2] as num).toDouble(),
    );
  }
}
