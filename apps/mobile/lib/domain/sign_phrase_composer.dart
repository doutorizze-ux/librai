class PhraseComposition {
  const PhraseComposition({
    required this.text,
    required this.isFinal,
    required this.glosses,
  });

  final String text;
  final bool isFinal;
  final List<String> glosses;
}

/// Converte uma sequência de glosas reconhecidas em português natural.
///
/// O reconhecimento visual continua responsável apenas por identificar cada
/// sinal. Regras de gênero e expressões compostas pertencem a esta camada
/// linguística, não ao modelo de visão.
class SignPhraseComposer {
  SignPhraseComposer({
    this.compositionWindow = const Duration(seconds: 12),
  });

  final Duration compositionWindow;

  String? _pendingGreeting;
  DateTime? _pendingSince;
  String? _latchedLabel;

  PhraseComposition? accept(
    String rawLabel, {
    DateTime? timestamp,
  }) {
    final now = timestamp ?? DateTime.now();
    final label = canonicalVisualLabel(rawLabel);

    if (label.isEmpty || _isNoise(label)) return null;
    if (_latchedLabel == label) return null;
    _latchedLabel = label;

    if (_pendingSince != null &&
        now.difference(_pendingSince!) > compositionWindow) {
      _clearPending();
    }

    final compoundGreeting = _compoundGreeting(label);
    if (compoundGreeting != null) {
      _clearPending();
      return compoundGreeting;
    }

    if (label == 'BOM' || label == 'BOA') {
      _pendingGreeting = 'BOM';
      _pendingSince = now;
      return const PhraseComposition(
        text: 'Bom/boa…',
        isFinal: false,
        glosses: ['BOM'],
      );
    }

    if (_pendingGreeting == 'BOM') {
      final greeting = _greetingFromSecondSign(label);
      _clearPending();
      if (greeting != null) return greeting;
    }

    return PhraseComposition(
      text: _literalText(label),
      isFinal: true,
      glosses: [label],
    );
  }

  /// Libera o sinal atual quando a mão sai da cena, permitindo repeti-lo.
  /// A expressão pendente é preservada para a pessoa executar o segundo sinal.
  void releaseCurrentSign() {
    _latchedLabel = null;
  }

  void reset() {
    _latchedLabel = null;
    _clearPending();
  }

  static String normalizeLabel(String rawLabel) {
    return rawLabel
        .trim()
        .toUpperCase()
        .replaceAll(RegExp(r'[!?,.;:]+'), '')
        .replaceAll(RegExp(r'[\s-]+'), '_')
        .replaceAll(RegExp(r'_+'), '_');
  }

  static String canonicalVisualLabel(String rawLabel) {
    final normalized = normalizeLabel(rawLabel);
    return normalized == 'BOA' ? 'BOM' : normalized;
  }

  /// Formata uma glosa técnica para apresentação ao usuário.
  ///
  /// O modelo continua usando rótulos canônicos em maiúsculas internamente,
  /// enquanto a interface mostra português com capitalização natural.
  static String displayLabel(String rawLabel) {
    final normalized = normalizeLabel(rawLabel);
    if (normalized.isEmpty) return '';
    if (normalized == 'OLA' || normalized == 'OLÁ') return 'Olá';
    if (normalized.length == 1) return normalized;
    const acronyms = {'CPF', 'RG', 'SUS', 'IA', 'LGPD'};
    if (acronyms.contains(normalized)) return normalized;
    final words = normalized.toLowerCase().replaceAll('_', ' ');
    return '${words[0].toUpperCase()}${words.substring(1)}';
  }

  /// Retorna os sinais que devem ser treinados separadamente quando o rótulo
  /// informado representa uma expressão composta conhecida.
  static List<String>? trainingComponentsFor(String rawLabel) {
    switch (normalizeLabel(rawLabel)) {
      case 'BOM_DIA':
      case 'BOA_DIA':
        return const ['BOM', 'DIA'];
      case 'BOM_TARDE':
      case 'BOA_TARDE':
        return const ['BOM', 'TARDE'];
      case 'BOM_NOITE':
      case 'BOA_NOITE':
        return const ['BOM', 'NOITE'];
    }
    return null;
  }

  bool _isNoise(String label) {
    return label == 'SINAL_DESCONHECIDO' ||
        label == 'DADOS_INSUFICIENTES' ||
        label == 'GESTO_DESCONHECIDO';
  }

  PhraseComposition? _compoundGreeting(String label) {
    switch (label) {
      case 'BOM_DIA':
      case 'BOA_DIA':
        return const PhraseComposition(
          text: 'Bom dia!',
          isFinal: true,
          glosses: ['BOM', 'DIA'],
        );
      case 'BOM_TARDE':
      case 'BOA_TARDE':
        return const PhraseComposition(
          text: 'Boa tarde!',
          isFinal: true,
          glosses: ['BOM', 'TARDE'],
        );
      case 'BOM_NOITE':
      case 'BOA_NOITE':
        return const PhraseComposition(
          text: 'Boa noite!',
          isFinal: true,
          glosses: ['BOM', 'NOITE'],
        );
    }
    return null;
  }

  PhraseComposition? _greetingFromSecondSign(String label) {
    switch (label) {
      case 'DIA':
        return const PhraseComposition(
          text: 'Bom dia!',
          isFinal: true,
          glosses: ['BOM', 'DIA'],
        );
      case 'TARDE':
        return const PhraseComposition(
          text: 'Boa tarde!',
          isFinal: true,
          glosses: ['BOM', 'TARDE'],
        );
      case 'NOITE':
        return const PhraseComposition(
          text: 'Boa noite!',
          isFinal: true,
          glosses: ['BOM', 'NOITE'],
        );
    }
    return null;
  }

  String _literalText(String label) {
    if (label == 'OLA' || label == 'OLÁ') return 'Olá.';
    final words = label.toLowerCase().replaceAll('_', ' ');
    return '${words[0].toUpperCase()}${words.substring(1)}.';
  }

  void _clearPending() {
    _pendingGreeting = null;
    _pendingSince = null;
  }
}
