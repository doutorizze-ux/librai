import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/data/datasources/vlibras_reference_remote_datasource.dart';

void main() {
  group('VlibrasReferenceRemoteDatasource.translatePortuguese', () {
    test('uses the API gateway translation when it is available', () async {
      final backendCalls = _RequestTracker();
      final officialCalls = _RequestTracker();
      final backend = _responseDio({
        'source_text': 'Olá tudo bem?',
        'gloss': 'OI TUDO_BEM [INTERROGAÇÃO]',
      }, backendCalls);
      final official = _responseDio('SHOULD NOT BE USED', officialCalls);
      final datasource = VlibrasReferenceRemoteDatasource(
        backend,
        officialTranslatorDio: official,
      );

      final translation = await datasource.translatePortuguese('Olá tudo bem?');

      expect(translation['gloss'], 'OI TUDO_BEM [INTERROGAÇÃO]');
      expect(backendCalls.calls, 1);
      expect(officialCalls.calls, 0);
    });

    test('falls back to the official service when the gateway is old',
        () async {
      final backendCalls = _RequestTracker();
      final officialCalls = _RequestTracker();
      final backend = _failingDio(backendCalls);
      final official = _responseDio(
        '  OI   TUDO_BEM [INTERROGAÇÃO]  ',
        officialCalls,
      );
      final datasource = VlibrasReferenceRemoteDatasource(
        backend,
        officialTranslatorDio: official,
      );

      final translation = await datasource.translatePortuguese('Olá tudo bem?');

      expect(translation['source_text'], 'Olá tudo bem?');
      expect(translation['gloss'], 'OI TUDO_BEM [INTERROGAÇÃO]');
      expect(backendCalls.calls, 1);
      expect(officialCalls.calls, 1);
      expect(officialCalls.lastPath, '/translate');
    });
  });
}

Dio _responseDio(Object responseData, _RequestTracker tracker) {
  final dio = Dio();
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        tracker.record(options.path);
        handler.resolve(
          Response<Object>(
            data: responseData,
            statusCode: 200,
            requestOptions: options,
          ),
        );
      },
    ),
  );
  return dio;
}

Dio _failingDio(_RequestTracker tracker) {
  final dio = Dio();
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        tracker.record(options.path);
        handler.reject(
          DioException(
            requestOptions: options,
            response: Response<void>(
              statusCode: 404,
              requestOptions: options,
            ),
            type: DioExceptionType.badResponse,
          ),
        );
      },
    ),
  );
  return dio;
}

class _RequestTracker {
  int calls = 0;
  String? lastPath;

  void record(String path) {
    calls++;
    lastPath = path;
  }
}
