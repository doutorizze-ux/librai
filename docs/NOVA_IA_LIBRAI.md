# Nova IA do Librai: critérios de produção

## Regra linguística

Uma classe do reconhecedor representa **uma unidade semântica de Libras**, não
uma palavra separada por espaços em português. Por isso, `TUDO BEM?` pode ser
treinado e reconhecido como um único sinal. Em contrapartida, uma expressão que
realmente exige dois sinais deve ser coletada como duas unidades distintas.

O backend normaliza espaços e maiúsculas para identificação, mas nunca divide
uma classe automaticamente pelo espaço do rótulo.

## O que é capturado

Durante o treinamento, o navegador processa os quadros em um Web Worker e envia
somente:

- 21 pontos por mão, com suporte a uma ou duas mãos;
- 13 pontos da parte superior do corpo;
- quatro proporções dinâmicas de expressão facial;
- instante de cada quadro e metadados não biométricos da coleta.

O vídeo e a malha facial bruta não são enviados nem persistidos.

Cada repetição é salva no PostgreSQL assim que termina. A quinta repetição fecha
o lote, mas as amostras permanecem em `pending_validation`; elas não contaminam
automaticamente o tradutor que está em produção.

## Barreira mínima antes de publicar um modelo

O pipeline padrão exige, por classe:

- pelo menos 3 professores independentes;
- pelo menos 15 amostras, normalmente 5 de cada professor;
- validação mantendo professores inteiros fora do treino;
- no mínimo 70% de acurácia na validação para gerar um candidato;
- hash SHA-256 conferido entre manifesto e ONNX;
- promoção explícita do manifesto para `production`.

Esses números são apenas a barreira inicial. Uma demonstração governamental não
deve ser chamada de tradução confiável antes de testes com surdos que não
participaram do treinamento, incluindo variações regionais, distâncias,
iluminação, velocidades e dominância manual diferentes.

## Resposta segura

O reconhecimento contínuo segmenta o início e o fim do movimento. Uma previsão
só é emitida quando:

- a confiança é pelo menos 85%; e
- a diferença para a segunda opção é pelo menos 12 pontos percentuais.

Baixa confiança, ambiguidade, ausência de modelo ou falha de inferência retornam
estado explícito e nenhuma palavra é inventada.

## API para parceiros

As chaves têm prefixo identificável, segredo exibido uma única vez e somente o
hash é persistido. Elas podem expirar e ser revogadas. O escopo atual para o
reconhecedor é `translation:recognize`, enviado no cabeçalho `X-Librai-Key`.

Endpoint externo:

`POST /v1/developer/recognition/chunks`

O serviço de inferência interno não é publicado diretamente. Sem um manifesto
de produção válido, a API responde `model_unavailable` em vez de usar pesos de
laboratório.

## Sequência operacional

1. Professores coletam cinco repetições por unidade semântica.
2. Exporta-se somente o dataset holístico v4.
3. `ml/training/train.py` treina e valida por professor separado.
4. `ml/training/export.py` gera ONNX somente para candidato aprovado.
5. O modelo é testado com usuários externos e revisado.
6. Somente então o manifesto é promovido e montado no serviço de inferência.
7. A versão anterior permanece disponível para reversão.
