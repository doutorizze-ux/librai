import '../entities/reference_sign.dart';
import '../repositories/reference_sign_repository.dart';

class SearchReferenceSigns {
  const SearchReferenceSigns(this._repository);

  final ReferenceSignRepository _repository;

  Future<List<ReferenceSign>> call(String query, {int limit = 100}) {
    return _repository.search(query: query.trim(), limit: limit);
  }
}
