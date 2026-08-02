import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class PendingTrainingRepetition {
  const PendingTrainingRepetition({
    required this.captureId,
    required this.trainerName,
    required this.signName,
    required this.platform,
    required this.cameraFacing,
    required this.frames,
  });

  final String captureId;
  final String trainerName;
  final String signName;
  final String platform;
  final String cameraFacing;
  final List<Map<String, dynamic>> frames;

  Map<String, dynamic> toJson() => {
        'capture_id': captureId,
        'trainer_name': trainerName,
        'sign_name': signName,
        'platform': platform,
        'camera_facing': cameraFacing,
        'frames': frames,
      };

  static PendingTrainingRepetition? fromJson(Object? value) {
    if (value is! Map) return null;
    final captureId = value['capture_id'];
    final trainerName = value['trainer_name'];
    final signName = value['sign_name'];
    final platform = value['platform'];
    final cameraFacing = value['camera_facing'];
    final rawFrames = value['frames'];
    if (captureId is! String ||
        trainerName is! String ||
        signName is! String ||
        platform is! String ||
        cameraFacing is! String ||
        rawFrames is! List) {
      return null;
    }
    final frames = rawFrames
        .whereType<Map>()
        .map((frame) => Map<String, dynamic>.from(frame))
        .toList(growable: false);
    if (frames.length != rawFrames.length || frames.isEmpty) return null;
    return PendingTrainingRepetition(
      captureId: captureId,
      trainerName: trainerName,
      signName: signName,
      platform: platform,
      cameraFacing: cameraFacing,
      frames: frames,
    );
  }
}

class TrainingDraftStore {
  static const _key = 'librai_pending_training_repetition_v1';

  Future<void> save(PendingTrainingRepetition repetition) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_key, jsonEncode(repetition.toJson()));
  }

  Future<PendingTrainingRepetition?> restore(String trainerName) async {
    final preferences = await SharedPreferences.getInstance();
    final encoded = preferences.getString(_key);
    if (encoded == null) return null;
    try {
      final repetition = PendingTrainingRepetition.fromJson(
        jsonDecode(encoded),
      );
      if (repetition == null || repetition.trainerName != trainerName) {
        return null;
      }
      return repetition;
    } catch (_) {
      await preferences.remove(_key);
      return null;
    }
  }

  Future<void> clear() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_key);
  }
}
