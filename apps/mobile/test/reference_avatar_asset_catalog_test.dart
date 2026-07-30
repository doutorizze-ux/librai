import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/data/reference_avatar_asset_catalog.dart';

void main() {
  group('ReferenceAvatarAssetCatalog', () {
    test('returns the realistic MetaHuman video for BOM', () {
      expect(
        ReferenceAvatarAssetCatalog.assetFor('bom'),
        'assets/avatar/signs/BOM.mp4',
      );
    });

    test('normalizes spaces and casing without guessing unsupported signs', () {
      expect(
        ReferenceAvatarAssetCatalog.assetFor('  Bom  '),
        'assets/avatar/signs/BOM.mp4',
      );
      expect(ReferenceAvatarAssetCatalog.assetFor('BOA_TARDE'), isNull);
    });
  });
}
