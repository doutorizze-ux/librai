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
