import 'package:dio/dio.dart';
import '../domain/interfaces/libras_translator.dart';

class LocalLibrasTranslator implements LibrasTranslator {
  final Dio _dio = Dio(BaseOptions(baseUrl: const String.fromEnvironment('API_URL', defaultValue: 'https://api.tvcatolica.site')));
  
  // Dicionário local de regras gramaticais para funcionamento Offline
  final Map<String, String> _offlineDictionary = {
    "BOM_DIA": "Bom dia!",
    "AJUDA": "Você pode me ajudar?",
    "SAÚDE": "Espero que você tenha saúde.",
    "EMERGÊNCIA": "Isto é uma emergência!",
    "EU AJUDA": "Eu preciso de ajuda.",
    "EU IR HOSPITAL": "Eu preciso ir ao hospital.",
    "VOCÊ IR HOSPITAL": "Você vai ao hospital?",
  };

  @override
  Future<String> translate(List<String> glosses, {required String sessionId}) async {
    if (glosses.isEmpty) return "";

    final String sequenceKey = glosses.join(' ').toUpperCase();

    try {
      // Tentar tradução avançada via API remota
      final response = await _dio.post(
        '/v1/translation/sessions/$sessionId/segments',
        data: {
          'text_detected': sequenceKey,
          'confidence': 0.95
        },
        options: Options(
          headers: {
            'Authorization': 'Bearer mock_admin_token_123', // Token simplificado de desenvolvimento
          },
          receiveTimeout: const Duration(seconds: 2),
          sendTimeout: const Duration(seconds: 2),
        )
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        // Retorna o resultado traduzido e estruturado pela API remota
        // Para o mock inicial, repete o texto ou usa um NLP básico
        final String textDetected = response.data['text_detected'] as String;
        
        // Se a API retornou o glosse, aplicamos o mapeamento estruturado
        return _applyLinguisticRules(textDetected);
      }
    } catch (e) {
      // Conexão falhou ou timeout -> Aciona o funcionamento degradado Offline de forma transparente
      print("[LibrasTranslator] Modo Offline Ativado devido a falha na rede: $e");
    }

    // Retorna tradução do dicionário local offline
    return _applyLinguisticRules(sequenceKey);
  }

  String _applyLinguisticRules(String rawSequence) {
    final String key = rawSequence.trim().toUpperCase();
    if (_offlineDictionary.containsKey(key)) {
      return _offlineDictionary[key]!;
    }
    
    // Fallback amigável de tradução literal se a sequência for desconhecida
    final words = key.split(' ').map((w) {
      if (_offlineDictionary.containsKey(w)) {
        return _offlineDictionary[w]!.replaceAll(RegExp(r'[!?.]'), '').toLowerCase();
      }
      return w.toLowerCase();
    }).join(' ');

    if (words.isEmpty) return "";
    return "${words[0].toUpperCase()}${words.substring(1)}.";
  }
}
