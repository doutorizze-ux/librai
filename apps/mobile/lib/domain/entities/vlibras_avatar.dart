enum VlibrasAvatar {
  hozana(
    playerId: 'hozana',
    displayName: 'Hozana',
    description: 'Avatar feminino',
  ),
  icaro(
    playerId: 'icaro',
    displayName: 'Ícaro',
    description: 'Avatar masculino',
  );

  const VlibrasAvatar({
    required this.playerId,
    required this.displayName,
    required this.description,
  });

  final String playerId;
  final String displayName;
  final String description;

  static VlibrasAvatar fromPlayerId(String? playerId) {
    return VlibrasAvatar.values.firstWhere(
      (avatar) => avatar.playerId == playerId,
      orElse: () => VlibrasAvatar.hozana,
    );
  }
}
