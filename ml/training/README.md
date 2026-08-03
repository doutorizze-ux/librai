# Treinamento temporal do Librai

Este diretório contém o pipeline candidato de reconhecimento de sinais
isolados. Ele não é ativado automaticamente no aplicativo.

## Garantias

- Não cria dados sintéticos.
- Não mistura o mesmo professor entre treino e validação.
- Exige, por padrão, 3 professores e 15 amostras por sinal.
- Reprova modelos abaixo de 70% na validação por professor.
- Exporta somente landmarks consentidos; nunca vídeo, áudio ou malha facial
  bruta.
- Um modelo aprovado recebe o estado `validated_ready_for_review`, não
  `deployed`.
- Um rótulo com espaços pode representar uma única unidade semântica de
  Libras. `TUDO BEM?`, por exemplo, não é dividido automaticamente.
- O treino de produção aceita somente a coleta holística v4; capturas antigas
  de mãos continuam preservadas, mas não entram silenciosamente no novo modelo.

## Preparação do computador

```powershell
python -m pip install -r ml\training\requirements.txt
```

No Windows com GPU AMD, o PyTorch padrão usa CPU. A aceleração DirectML deve
ser medida separadamente antes de ser adotada.

## Exportar o dataset

Execute dentro de um ambiente que tenha acesso ao PostgreSQL:

```powershell
python ml\training\export_dataset.py `
  --database-url "postgresql://..." `
  --output "C:\caminho-privado\training.json"
```

O diretório `ml/dataset/private` deve permanecer fora do Git.

## Treinar

```powershell
python ml\training\train.py "C:\caminho-privado\training.json"
```

O comando falha de forma explícita se os dados forem insuficientes ou se o
modelo não generalizar para o professor mantido fora do treino.

## Exportar para revisão

```powershell
python ml\training\export.py ml\models\candidate
```

Publicar o ONNX ou convertê-lo para o formato móvel é uma etapa posterior e
deliberada. Nenhum peso aleatório pode ser exportado.

Depois dos testes externos e da aprovação responsável, a promoção repete os
gates, confere o hash e cria o único manifesto aceito pelo servidor:

```powershell
python ml\training\promote.py `
  ml\models\review\librai_stgcn.manifest.json `
  --approved-by "Comitê Librai"
```

## Vídeos autorizados

Os vídeos autorizados ficam em `ml/dataset/private/videos/inbox` e nunca são
versionados. O fluxo local é:

1. `inventory_videos.py` inventaria arquivos e duração.
2. `register_video_sources.py` registra autoria e autorização.
3. `discover_video_labels.py` e `build_segment_review.py` propõem segmentos.
4. `extract_holistic_dataset.py` trata vídeos temporais.
5. `extract_spatial_grid_dataset.py` trata vídeos com vários sinais em grade.
6. `merge_extracted_datasets.py` corrige somente rótulos verificados,
   coloca ambiguidades em quarentena e consolida landmarks.

Os vídeos brutos não entram no treinamento. O dataset consolidado contém
somente landmarks temporais de mãos, pose e medidas dinâmicas de expressão.
Uma repetição ou recorte do mesmo vídeo continua contando como uma única fonte,
para evitar métricas artificialmente infladas.

## Piloto externo MINDS → MALTA

O piloto externo verifica se o reconhecedor aprende movimento de Libras em vez
de memorizar cenário ou pessoa. Ele não publica pesos no aplicativo.

1. O treino usa uma recompactação de 320 vídeos do
   [MINDS-Libras](https://doi.org/10.5281/zenodo.2667329), cuja base canônica é
   CC BY 4.0: 20 sinais, 8 sinalizadores e 2 repetições.
2. Uma pessoa inteira do MINDS fica fora do treino para validação interna.
3. A prova final usa 99 tensores do MALTA-LIBRAS, com 19 sinais e fontes
   visuais diferentes. O MALTA é somente avaliação; nunca é misturado ao
   treino deste piloto.
4. O modelo é reprovado para implantação se não alcançar simultaneamente 70%
   top-1 na pessoa separada e 70% top-1 no teste externo.
5. Os quadros RGB são processados em memória e descartados. Somente landmarks
   de mãos/pose e quatro proporções dinâmicas de expressão são mantidos.

Preparar e verificar os arquivos privados:

```powershell
python ml\training\prepare_minds_malta_pilot.py `
  --output-dir ml\dataset\private\minds-malta-pilot
```

Extrair os landmarks sem reter imagens:

```powershell
python ml\training\extract_external_pilot_landmarks.py `
  ml\dataset\private\minds-malta-pilot\manifest.json `
  --model-dir ml\models\mediapipe `
  --output-dir ml\dataset\private\minds-malta-pilot\landmarks
```

Executar primeiro a validação alinhada ao APK e ao endpoint atual, que recebem
somente as duas mãos:

```powershell
.\ml\.venv-directml\Scripts\python.exe `
  ml\training\evaluate_minds_malta_hands_pilot.py `
  ml\dataset\private\minds-malta-pilot\landmarks\train_landmarks.json `
  ml\dataset\private\minds-malta-pilot\landmarks\external_test_landmarks.json `
  --directml
```

O resultado fica em
`ml/dataset/private/minds-malta-pilot/hands-evaluation/evaluation.json`. O status
`rejected_not_for_deployment` bloqueia qualquer uso dos pesos no produto.

O experimento `evaluate_minds_malta_pilot.py` usa também pose corporal e
expressão. Ele é uma linha de pesquisa separada: não pode ser implantado até o
APK capturar o mesmo esquema de features nativamente.
