# Risk Register - Sinaliza AI

Este documento cataloga os riscos críticos identificados para o projeto **Sinaliza AI**, categorizando probabilidade (P), impacto (I), severidade (S = P * I) e suas respectivas estratégias de mitigação.

---

## 1. Riscos de Engenharia e Performance

### R-1.1: Superaquecimento do Aparelho e Consumo Excessivo de Bateria
- **Descrição**: Inferência computacional pesada e contínua de landmarks de vídeo (MediaPipe + ONNX) pode esgotar a bateria e travar o celular do usuário.
- **P**: Alta | **I**: Alta | **S**: Crítico
- **Mitigação**: 
  - Ajuste dinâmico de taxa de frames de processamento de inferência (inferir a cada 2 ou 3 frames em vez de rodar a 30 FPS inteiros).
  - Implementação de "Modo Economia de Energia" automático quando a bateria estiver abaixo de 20%.

### R-1.2: Latência Elevada nas Respostas
- **Descrição**: Buffer de frames e inferência sequencial demorando mais de 500ms, prejudicando a fluidez da comunicação real.
- **P**: Média | **I**: Alta | **S**: Alto
- **Mitigação**: 
  - Execução de pipeline de landmarks assíncrono em Dart Isolates (multithreading).
  - Quantização pós-treinamento de modelos (INT8 em vez de FP32) para aceleração via NPU/GPU no celular.

---

## 2. Riscos Linguísticos e Sociais

### R-2.1: Tradução Alucinada (Falsas Promessas)
- **Descrição**: O modelo tentar prever um sinal com baixa confiança e gerar uma tradução errada, induzindo o usuário ouvinte a erro grave (especialmente em ambientes de saúde/hospitais).
- **P**: Média | **I**: Crítica | **S**: Crítico
- **Mitigação**: 
  - **Filtro de Segurança**: Se o nível de confiança estiver abaixo do configurado (ex: 75%), o app nunca exibirá texto inventado. Mostrará "Não consegui reconhecer o sinal com segurança".
  - Declaração de limitação de responsabilidade explícita em todas as telas (Disclaimers).

### R-2.2: Reducionismo de Libras a "Português Gesticulado"
- **Descrição**: Desconsiderar expressões não manuais (face/olhar) ou a gramática própria de Libras e tentar mapear gestos individuais diretamente em português escrito sintaticamente idêntico.
- **P**: Alta | **I**: Alta | **S**: Crítico
- **Mitigação**:
  - Inclusão obrigatória de especialistas surdos e intérpretes na validação da arquitetura do modelo de decodificação sequencial.
  - Treinamento do modelo considerando landmarks faciais e corporais, e não apenas a geometria dos dedos.

---

## 3. Riscos Jurídicos e de Privacidade (LGPD)

### R-3.1: Enquadramento de Landmarks como Dado Biométrico
- **Descrição**: Questionamentos legais sobre a extração de landmarks faciais do usuário configurar captura de biometria sem bases legais adequadas.
- **P**: Baixa | **I**: Crítica | **S**: Alto
- **Mitigação**:
  - Garantir o descarte de frames originais imediatamente na RAM (descarte em milissegundos).
  - Mapear a base legal como Execução de Contrato e Consentimento explícito, demonstrando tecnicamente que o vetor de landmarks geométricos não permite reconstituição facial estática ou identificação de biometria de acesso.
