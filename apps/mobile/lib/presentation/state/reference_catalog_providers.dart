import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/datasources/vlibras_reference_remote_datasource.dart';
import '../../data/repositories/reference_sign_repository_impl.dart';
import '../../domain/entities/reference_sign.dart';
import '../../domain/entities/reference_motion.dart';
import '../../domain/entities/reference_sequence.dart';
import '../../domain/entities/reference_translation.dart';
import '../../domain/repositories/reference_sign_repository.dart';
import '../../domain/usecases/search_reference_signs.dart';
import '../../platform/app_config.dart';

final referenceSignRepositoryProvider =
    Provider<ReferenceSignRepository>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: AppConfig.apiUrl,
      connectTimeout: const Duration(seconds: 8),
      receiveTimeout: const Duration(seconds: 8),
    ),
  );
  final officialTranslatorDio = Dio(
    BaseOptions(
      baseUrl: 'https://traducao2.vlibras.gov.br',
      connectTimeout: const Duration(seconds: 8),
      receiveTimeout: const Duration(seconds: 12),
      headers: kIsWeb
          ? const <String, String>{}
          : const {
              'Origin': 'https://doutorizze-ux.github.io',
              'Referer': 'https://doutorizze-ux.github.io/librai/',
            },
    ),
  );
  ref.onDispose(() {
    dio.close();
    officialTranslatorDio.close();
  });
  return ReferenceSignRepositoryImpl(
    VlibrasReferenceRemoteDatasource(
      dio,
      officialTranslatorDio: officialTranslatorDio,
    ),
  );
});

final searchReferenceSignsProvider = Provider<SearchReferenceSigns>((ref) {
  return SearchReferenceSigns(ref.watch(referenceSignRepositoryProvider));
});

final referenceCatalogProvider =
    FutureProvider.family<List<ReferenceSign>, String>((ref, query) {
  return ref.watch(searchReferenceSignsProvider)(query);
});

final referenceMotionProvider =
    FutureProvider.family<ReferenceMotion, String>((ref, label) {
  return ref.watch(referenceSignRepositoryProvider).loadMotion(label);
});

final referenceSequenceProvider =
    FutureProvider.family<ReferenceSequence, String>((ref, text) {
  return ref.watch(referenceSignRepositoryProvider).compose(text);
});

final referenceTranslationProvider =
    FutureProvider.family<ReferenceTranslation, String>((ref, text) {
  return ref.watch(referenceSignRepositoryProvider).translatePortuguese(text);
});
