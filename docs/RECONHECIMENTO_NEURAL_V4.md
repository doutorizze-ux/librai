# Reconhecimento neural LibrAI v4

## Estado seguro da migração

O aplicativo ainda não deve enviar usuários ao modelo neural até existir um
artefato ONNX aprovado. A rota contínua e o serviço de inferência estão
preparados, porém a ausência de um modelo agora aparece explicitamente em
`GET /ready` com HTTP 503. `GET /live` informa somente que o processo está vivo.

A tradução v4 anterior continua sendo um protótipo por comparação temporal.
Ela lê apenas capturas `validated_capture`; lotes `pending_validation` são
ignorados. Portanto, uma coleta bruta ou importada não entra silenciosamente
no tradutor.

## Fluxo da coleta

1. Cada repetição aceita é salva imediatamente com um `capture_id` idempotente.
2. Enquanto há menos de cinco repetições, o estado é `collecting`.
3. Na quinta repetição, as cinco sequências são comparadas entre si.
4. Se uma captura for discrepante, ela é removida, as outras quatro são
   preservadas e a resposta retorna `retake_required`.
5. Se o conjunto for coerente, as cinco amostras recebem
   `validated_capture` e podem ser exportadas para treinamento.

O validador mede coerência interna; ele não prova que o rótulo informado está
linguisticamente correto. A validação com professores diferentes e usuários
não vistos continua obrigatória.

## Gates obrigatórios do ONNX

Um novo modelo somente pode ser promovido quando cumprir todos os gates:

- formato holístico v4 e arquitetura ST-GCN;
- ao menos três professores e quinze amostras por classe;
- validação separando professores inteiros, sem vazamento entre treino e teste;
- acurácia de validação mínima de 70%;
- matriz de confusão e precisão, recall e F1 por sinal;
- pelo menos trinta sequências OOD (sinais fora do vocabulário e movimentos que
  não são sinais);
- aceitação de sinais conhecidos de pelo menos 70%;
- rejeição OOD de pelo menos 90%;
- limiares de confiança e margem gravados no manifesto e usados em execução;
- hash do ONNX, revisão humana e promoção explícita.

Esses números são gates iniciais, não promessa de precisão comercial. Devem
subir conforme a base real crescer.

## Comandos do pipeline

```powershell
python ml/training/export_dataset.py --database-url $env:DATABASE_URL --output ml/dataset/private/training.json

python ml/training/train.py ml/dataset/private/training.json `
  --ood-dataset ml/dataset/private/ood-validation.json `
  --output-dir ml/models/candidate

python ml/training/export.py ml/models/candidate `
  --output ml/models/review/librai_stgcn.onnx

python ml/training/promote.py ml/models/review/librai_stgcn.manifest.json `
  --output-dir ml/models/production `
  --approved-by "Responsável pela validação"
```

Depois da promoção, o serviço deve ser reiniciado e `GET /ready` precisa
responder HTTP 200 com o identificador do modelo. Só então o aplicativo pode
trocar o comparador v4 pela rota neural contínua.

## Próximo marco

O próximo marco depende de dados reais: montar um piloto pequeno com classes
prioritárias, três professores por classe, usuários não vistos e um conjunto
OOD explícito. O primeiro ONNX será avaliado em modo sombra antes de controlar
a tradução mostrada ao usuário.
