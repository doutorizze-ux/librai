import '../entities/assisted_prediction.dart';

abstract interface class AssistedSignInterpreter {
  Future<AssistedPrediction> predict(List<Map<String, dynamic>> frames);
}
