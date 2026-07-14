import 'package:flutter_test/flutter_test.dart';
import 'package:sinaliza_ai/domain/vision_validator.dart';
import 'package:sinaliza_ai/presentation/state/landmark_buffer.dart';
import 'package:sinaliza_ai/platform/mock_interpreter.dart';
import 'package:sinaliza_ai/presentation/state/glosses_buffer.dart';
import 'package:sinaliza_ai/platform/local_translator.dart';
import 'package:sinaliza_ai/data/datasources/local_history_storage.dart';

void main() {
  group('Testes do Buffer Temporal (LandmarkBuffer)', () {
    test('Deve adicionar frames corretamente até o limite máximo (FIFO)', () {
      final buffer = LandmarkBuffer(maxFrames: 5);

      // Adicionar 3 frames
      buffer.addFrame([{'x': 0.1, 'y': 0.1, 'z': 0.0}]);
      buffer.addFrame([{'x': 0.2, 'y': 0.2, 'z': 0.0}]);
      buffer.addFrame([{'x': 0.3, 'y': 0.3, 'z': 0.0}]);

      expect(buffer.currentSize, equals(3));

      // Adicionar mais 3 frames (totalizando 6, estourando o limite de 5)
      buffer.addFrame([{'x': 0.4, 'y': 0.4, 'z': 0.0}]);
      buffer.addFrame([{'x': 0.5, 'y': 0.5, 'z': 0.0}]);
      buffer.addFrame([{'x': 0.6, 'y': 0.6, 'z': 0.0}]);

      // Tamanho do buffer deve travar em 5
      expect(buffer.currentSize, equals(5));

      // O primeiro frame (0.1, 0.1) deve ter sido descartado. O primeiro agora é (0.2, 0.2)
      final flatData = buffer.getFlattenedData();
      expect(flatData.first, equals(0.2));
    });

    test('Deve aplicar Backpressure (descartar frames) quando ocupado', () {
      final buffer = LandmarkBuffer(maxFrames: 5);

      // Inicia sem processamento
      expect(buffer.isProcessing, isFalse);

      // Adiciona um frame
      final added1 = buffer.addFrame([{'x': 0.5, 'y': 0.5, 'z': 0.0}]);
      expect(added1, isTrue);

      // Sinaliza processamento ocupado
      buffer.setProcessing(true);
      expect(buffer.isProcessing, isTrue);

      // Tenta adicionar frame
      final added2 = buffer.addFrame([{'x': 0.6, 'y': 0.6, 'z': 0.0}]);
      expect(added2, isFalse); // Deve descartar por backpressure
      expect(buffer.currentSize, equals(1));

      // Conclui processamento
      buffer.setProcessing(false);
      final added3 = buffer.addFrame([{'x': 0.7, 'y': 0.7, 'z': 0.0}]);
      expect(added3, isTrue);
      expect(buffer.currentSize, equals(2));
    });
  });

  group('Testes do Validador de Enquadramento (VisionValidator)', () {
    test('Deve detectar ausência de pessoa quando landmarks são nulos ou vazios', () {
      final state1 = VisionValidator.validateFraming(null, true);
      expect(state1, equals(VisionState.waitingPerson));

      final state2 = VisionValidator.validateFraming([], true);
      expect(state2, equals(VisionState.waitingPerson));
    });

    test('Deve alertar se o rosto não for detectado', () {
      final landmarks = [{'x': 0.5, 'y': 0.5, 'z': 0.0}];
      final state = VisionValidator.validateFraming(landmarks, false);
      expect(state, equals(VisionState.faceOutOfFrame));
    });

    test('Deve validar como OK quando landmarks estão centralizados e proporcionais', () {
      // Landmarks com espalhamento médio (~0.3) e centralizados
      final landmarks = [
        {'x': 0.4, 'y': 0.5, 'z': 0.0},
        {'x': 0.6, 'y': 0.5, 'z': 0.0},
      ];
      final state = VisionValidator.validateFraming(landmarks, true);
      expect(state, equals(VisionState.ok));
    });

    test('Deve alertar para aproximar-se se o espalhamento for muito pequeno (sinalizador longe)', () {
      final landmarks = [
        {'x': 0.49, 'y': 0.5, 'z': 0.0},
        {'x': 0.51, 'y': 0.5, 'z': 0.0},
      ];
      final state = VisionValidator.validateFraming(landmarks, true);
      expect(state, equals(VisionState.stepCloser));
    });

    test('Deve alertar para afastar-se se o espalhamento for muito grande (sinalizador muito próximo)', () {
      final landmarks = [
        {'x': 0.1, 'y': 0.5, 'z': 0.0},
        {'x': 0.8, 'y': 0.5, 'z': 0.0},
      ];
      final state = VisionValidator.validateFraming(landmarks, true);
      expect(state, equals(VisionState.stepBack));
    });

    test('Deve alertar se as mãos saírem da tela lateralmente', () {
      final landmarks = [
        {'x': 0.01, 'y': 0.5, 'z': 0.0},
      ];
      final state = VisionValidator.validateFraming(landmarks, true);
      expect(state, equals(VisionState.handsOutOfFrame));
    });
  });

  group('Testes do Interpretador de Sinais (MockSignInterpreter)', () {
    test('Deve falhar se tentar inferir sem carregar o modelo', () {
      final interpreter = MockSignInterpreter();
      expect(
        () => interpreter.predict([{'x': 0.5, 'y': 0.5, 'z': 0.0}]),
        throwsStateError
      );
    });

    test('Deve validar landmarks e prever sinal conhecido com alta confiança', () async {
      final interpreter = MockSignInterpreter();
      await interpreter.loadModel("test_assets/weights.json");

      // Landmarks com média X próxima a 0.5 (AJUDA)
      final result = await interpreter.predict([
        {'x': 0.49, 'y': 0.5, 'z': 0.0},
        {'x': 0.51, 'y': 0.5, 'z': 0.0},
      ]);

      expect(result.label, equals("AJUDA"));
      expect(result.confidence, greaterThanOrEqualTo(0.75));
      expect(result.isTestFixture, isTrue);
    });

    test('Deve rejeitar sinal com "SINAL_DESCONHECIDO" se a confiança for baixa', () async {
      final interpreter = MockSignInterpreter();
      await interpreter.loadModel("test_assets/weights.json");

      // Landmarks com média X longe dos limites conhecidos (ex: 0.1)
      final result = await interpreter.predict([
        {'x': 0.1, 'y': 0.5, 'z': 0.0},
        {'x': 0.12, 'y': 0.5, 'z': 0.0},
      ]);

      // Deve cair na rejeição e retornar "SINAL_DESCONHECIDO"
      expect(result.label, equals("SINAL_DESCONHECIDO"));
      expect(result.confidence, lessThan(0.75));
    });
  });

  group('Testes do Buffer de Sinais (GlossesBuffer)', () {
    test('Deve deduplicar sinais consecutivos e filtrar ruído', () {
      final buffer = GlossesBuffer();

      // Adiciona sinais repetidos
      buffer.addGloss("AJUDA");
      buffer.addGloss("AJUDA");
      buffer.addGloss("AJUDA");

      expect(buffer.length, equals(1));
      expect(buffer.glosses.first, equals("AJUDA"));

      // Tenta adicionar ruído do sistema de rejeição
      buffer.addGloss("SINAL_DESCONHECIDO");
      buffer.addGloss("DADOS_INSUFICIENTES");
      
      expect(buffer.length, equals(1)); // Deve manter apenas o sinal válido

      // Adiciona novo sinal
      buffer.addGloss("SAÚDE");
      expect(buffer.length, equals(2));
      expect(buffer.toString(), equals("AJUDA SAÚDE"));
    });
  });

  group('Testes do Tradutor de Libras (LocalLibrasTranslator)', () {
    test('Deve traduzir frase estruturada localmente (Offline fallback)', () async {
      final translator = LocalLibrasTranslator();

      final result1 = await translator.translate(["EU", "IR", "HOSPITAL"], sessionId: "session_test");
      expect(result1, equals("Eu preciso ir ao hospital."));

      final result2 = await translator.translate(["BOM_DIA"], sessionId: "session_test");
      expect(result2, equals("Bom dia!"));
    });

    test('Deve efetuar tradução literal em caso de sequência desconhecida', () async {
      final translator = LocalLibrasTranslator();

      final result = await translator.translate(["CASA", "AZUL"], sessionId: "session_test");
      expect(result, equals("Casa azul."));
    });
  });

  group('Testes de Armazenamento Local de Histórico (LocalHistoryStorage)', () {
    test('Deve salvar e exportar histórico de conversação', () {
      final storage = LocalHistoryStorage();

      final session = TranslationSession(
        id: "session_abc",
        timestamp: DateTime.now(),
        transcript: ["Ouvinte: Oi", "Surdo: Olá"],
      );

      storage.saveSession(session);
      expect(storage.getSessions().length, equals(1));
      
      final jsonStr = storage.exportSessionsAsJson();
      expect(jsonStr, contains("session_abc"));
    });

    test('Deve descartar sessões com mais de 30 dias (Conformidade LGPD)', () {
      final storage = LocalHistoryStorage();

      // Sessão recente (2 dias atrás)
      final sessionRecent = TranslationSession(
        id: "session_recent",
        timestamp: DateTime.now().subtract(const Duration(days: 2)),
        transcript: ["Recent"],
      );

      // Sessão antiga (35 dias atrás)
      final sessionOld = TranslationSession(
        id: "session_old",
        timestamp: DateTime.now().subtract(const Duration(days: 35)),
        transcript: ["Old"],
      );

      storage.saveSession(sessionRecent);
      storage.saveSession(sessionOld);

      expect(storage.getSessions().length, equals(2));

      // Executa o descarte LGPD
      final removed = storage.cleanupOldSessions(maxAgeDays: 30);
      expect(removed, equals(1));
      expect(storage.getSessions().length, equals(1));
      expect(storage.getSessions().first.id, equals("session_recent"));
    });
  });
}
