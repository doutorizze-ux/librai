import 'dart:convert';

class TranslationSession {
  final String id;
  final DateTime timestamp;
  final List<String> transcript;

  TranslationSession({
    required this.id,
    required this.timestamp,
    required this.transcript,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'timestamp': timestamp.toIso8601String(),
      'transcript': transcript,
    };
  }

  factory TranslationSession.fromMap(Map<String, dynamic> map) {
    return TranslationSession(
      id: map['id'] as String,
      timestamp: DateTime.parse(map['timestamp'] as String),
      transcript: List<String>.from(map['transcript'] as List),
    );
  }
}

class LocalHistoryStorage {
  // Simulador de persistência local na RAM (comportamento offline seguro)
  final List<TranslationSession> _inMemoryDatabase = [];

  List<TranslationSession> get activeSessions => List.unmodifiable(_inMemoryDatabase);

  void saveSession(TranslationSession session) {
    // Remover duplicados se houver salvamento contínuo
    _inMemoryDatabase.removeWhere((s) => s.id == session.id);
    _inMemoryDatabase.add(session);
  }

  List<TranslationSession> getSessions() {
    return activeSessions;
  }

  // PRIVACIDADE LGPD: Limpeza e descarte automático de dados biométricos/transcrições antigas
  int cleanupOldSessions({int maxAgeDays = 30}) {
    final now = DateTime.now();
    int removedCount = 0;

    _inMemoryDatabase.removeWhere((session) {
      final difference = now.difference(session.timestamp).inDays;
      if (difference >= maxAgeDays) {
        removedCount++;
        return true;
      }
      return false;
    });

    return removedCount;
  }

  // Exportação em formato estruturado JSON de auditoria
  String exportSessionsAsJson() {
    final list = _inMemoryDatabase.map((s) => s.toMap()).toList();
    return jsonEncode(list);
  }

  void clearAll() {
    _inMemoryDatabase.clear();
  }
}
