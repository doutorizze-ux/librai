class GlossesBuffer {
  final List<String> _glosses = [];

  List<String> get glosses => List.unmodifiable(_glosses);
  int get length => _glosses.length;

  // Adiciona um glosse aplicando filtro de deduplicação e ruído
  bool addGloss(String gloss) {
    // Ignorar códigos de erro e sinais desconhecidos (filtro de ruído)
    if (gloss == "SINAL_DESCONHECIDO" || 
        gloss == "DADOS_INSUFICIENTES" || 
        gloss == "GESTO_DESCONHECIDO" ||
        gloss.trim().isEmpty) {
      return false;
    }

    // Deduplicação: não adiciona se for idêntico ao último glosse inserido
    if (_glosses.isNotEmpty && _glosses.last == gloss) {
      return false;
    }

    _glosses.add(gloss);
    return true;
  }

  // Limpa a fila de glosses acumulados
  void clear() {
    _glosses.clear();
  }

  @override
  String toString() {
    return _glosses.join(' ');
  }
}
