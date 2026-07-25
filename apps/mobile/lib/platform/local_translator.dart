import '../domain/interfaces/libras_translator.dart';

class LocalLibrasTranslator implements LibrasTranslator {
  final Map<String, String> _offlineDictionary = {
    'BOM_DIA': 'Bom dia!',
    'BOM DIA': 'Bom dia!',
    'BOA DIA': 'Bom dia!',
    'BOM TARDE': 'Boa tarde!',
    'BOA TARDE': 'Boa tarde!',
    'BOM NOITE': 'Boa noite!',
    'BOA NOITE': 'Boa noite!',
    'AJUDA': 'Você pode me ajudar?',
    'SAÚDE': 'Espero que você tenha saúde.',
    'EMERGÊNCIA': 'Isto é uma emergência!',
    'EU AJUDA': 'Eu preciso de ajuda.',
    'EU IR HOSPITAL': 'Eu preciso ir ao hospital.',
    'VOCÊ IR HOSPITAL': 'Você vai ao hospital?',
  };

  @override
  Future<String> translate(
    List<String> glosses, {
    required String sessionId,
  }) async {
    if (glosses.isEmpty) return '';

    // Camera feedback must never wait for the network. Persisting a session is
    // a separate data-layer operation and cannot delay local translation.
    return _applyLinguisticRules(glosses.join(' ').toUpperCase());
  }

  String _applyLinguisticRules(String rawSequence) {
    final key = rawSequence.trim().toUpperCase();
    final structured = _offlineDictionary[key];
    if (structured != null) return structured;

    final words = key.split(' ').map((word) {
      final mapped = _offlineDictionary[word];
      if (mapped != null) {
        return mapped.replaceAll(RegExp(r'[!?.]'), '').toLowerCase();
      }
      return word.toLowerCase();
    }).join(' ');

    if (words.isEmpty) return '';
    return '${words[0].toUpperCase()}${words.substring(1)}.';
  }
}
