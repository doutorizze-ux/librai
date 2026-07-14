# ADR 0002: Tecnologias de Inferência de Visão Computacional

## Status
Aprovado

## Contexto
O processamento e tradução de sinais de Libras requerem o rastreamento em alta fidelidade de mãos (landmarks), expressões faciais (não manuais) e postura (pose corporal). O processamento de imagens e frames inteiros de vídeo no servidor consome muita banda de rede e infraestrutura de GPU cara, além de ferir os princípios de privacidade por padrão (LGPD).

## Decisão
Decidimos utilizar a biblioteca **MediaPipe** localmente no dispositivo para extrair as coordenadas dos landmarks estruturais (mãos, face, postura). 
- Para a inferência local de sinais básicos e alfabeto, utilizaremos o **ONNX Runtime Mobile / TFLite**.
- Os frames brutos do vídeo serão processados na memória RAM volátil e imediatamente destruídos após a extração dos landmarks de coordenadas matemáticas.
- Para processamentos complexos na nuvem, o aplicativo transmitirá apenas as coordenadas de landmarks via WebSocket, preservando a identidade física do sinalizador.

## Consequências
- **Positivas**:
  - Privacidade por design (LGPD): Nenhum rosto ou vídeo contendo imagens pessoais é transmitido ao servidor.
  - Consumo de rede mínimo: Landmarks normalizados ocupam menos de 10KB por frame, comparado a megabytes de um fluxo de vídeo contínuo.
  - Baixa latência: A detecção básica funciona localmente e de forma offline.
- **Negativas**:
  - Exigência de hardware básico para rodar o MediaPipe localmente a pelo menos 15 FPS (atendido pela grande maioria dos smartphones atuais).
