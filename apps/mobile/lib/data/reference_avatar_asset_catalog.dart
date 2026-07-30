class ReferenceAvatarAssetCatalog {
  const ReferenceAvatarAssetCatalog._();

  static const Map<String, String> _assetsByLabel = {
    'BOM': 'assets/avatar/signs/BOM.mp4',
  };

  static String? assetFor(String label) {
    return _assetsByLabel[_normalize(label)];
  }

  static String _normalize(String label) {
    return label.trim().replaceAll(RegExp(r'\s+'), '_').toUpperCase();
  }
}
