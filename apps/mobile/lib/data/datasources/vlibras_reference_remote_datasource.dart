import 'package:dio/dio.dart';

class VlibrasReferenceRemoteDatasource {
  VlibrasReferenceRemoteDatasource(this._dio);

  final Dio _dio;

  Future<List<Map<String, dynamic>>> search({
    required String query,
    required int offset,
    required int limit,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/vlibras-reference/catalog',
      queryParameters: {
        'query': query,
        'offset': offset,
        'limit': limit,
      },
    );
    final rawSigns = response.data?['signs'];
    if (rawSigns is! List) {
      throw const FormatException('Resposta inválida do catálogo de Libras');
    }
    return rawSigns
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> loadMotion(String label) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/vlibras-reference/motions/${Uri.encodeComponent(label)}',
    );
    final data = response.data;
    if (data == null || data['frames'] is! List) {
      throw const FormatException('Animação de Libras inválida');
    }
    return data;
  }

  Future<Map<String, dynamic>> compose(String text) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/vlibras-reference/compose',
      data: {'text': text},
    );
    final data = response.data;
    if (data == null || data['signs'] is! List) {
      throw const FormatException('Sequência de Libras inválida');
    }
    return data;
  }

  Future<Map<String, dynamic>> translatePortuguese(String text) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/vlibras-reference/translate',
      data: {'text': text},
    );
    final data = response.data;
    if (data == null ||
        data['source_text'] is! String ||
        data['gloss'] is! String) {
      throw const FormatException('Tradução oficial de Libras inválida');
    }
    return data;
  }
}
