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
    this.formatVersion = 3,
    this.regionalVariation = 'Não informado',
    this.dominantHand = 'Unknown',
  });

  final String captureId;
  final String trainerName;
  final String signName;
  final String platform;
  final String cameraFacing;
  final List<Map<String, dynamic>> frames;
  final int formatVersion;
  final String regionalVariation;
  final String dominantHand;

  Map<String, dynamic> toJson() => {
        'capture_id': captureId,
        'trainer_name': trainerName,
        'sign_name': signName,
        'platform': platform,
        'camera_facing': cameraFacing,
        'frames': frames,
        'format_version': formatVersion,
        'regional_variation': regionalVariation,
        'dominant_hand': dominantHand,
      };

  static PendingTrainingRepetition? fromJson(Object? value) {
    if (value is! Map) return null;
    final captureId = value['capture_id'];
    final trainerName = value['trainer_name'];
    final signName = value['sign_name'];
    final platform = value['platform'];
    final cameraFacing = value['camera_facing'];
    final rawFrames = value['frames'];
    final rawFormatVersion = value['format_version'];
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
      formatVersion: rawFormatVersion is num ? rawFormatVersion.toInt() : 3,
      regionalVariation:
          value['regional_variation']?.toString() ?? 'Não informado',
      dominantHand: value['dominant_hand']?.toString() ?? 'Unknown',
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
