# Machine Learning Strategy - Sinaliza AI

Este documento descreve a estratégia de Machine Learning, as métricas avaliadas, o Model Registry e os critérios de deploy dos modelos do **Sinaliza AI**.

---

## 1. Arquitetura de Modelagem de Sinais (Libras)
Como Libras possui aspectos espaciais e temporais (movimento das mãos, pose do corpo, expressões não manuais), a arquitetura do modelo de IA deve suportar diferentes implementações acopladas por uma interface de inferência comum:

- **ST-GCN (Spatial-Temporal Graph Convolutional Network)**: Processamento de landmarks das mãos e pose como gráficos (nodes = articulações, edges = conexões físicas e temporais).
- **Temporal Transformer**: Codificação de características sequenciais com atenção temporal para capturar a duração e transições de sinais.
- **LSTM / GRU**: Modelos de baseline rápidos para rodar offline em aparelhos de baixo processamento.
- **Encoder-Decoder com CTC (Connectionist Temporal Classification)**: Para tradução contínua, permitindo mapear frames contínuos para sequências de glosses.

---

## 2. Métricas de Avaliação do Modelo

Para homologação de qualquer modelo antes de ir a produção, calculamos as seguintes métricas em nosso conjunto de testes:

### 2.1. Métricas Linguísticas e de Classificação
- **Top-1 / Top-3 Accuracy**: Percentual de vezes que o sinal correto é classificado no topo das predições do modelo.
- **F1-Macro / F1 por Classe**: Média harmônica de precisão e recall para garantir que sinais raros (ex: termos de saúde) não sejam dominados por termos frequentes (ex: saudações).
- **WER (Word Error Rate)** e **SER (Sign Error Rate)**: Erro de edição na tradução contínua de frases.
- **ECE (Expected Calibration Error)**: Mede quão alinhada a probabilidade de saída do modelo está com a taxa de acerto real (calibração de confiança).

### 2.2. Métricas de Hardware e Operação
- **Latência P50, P95, P99**: Tempo de processamento da inferência local/servidor.
- **Max Memory (RAM)** e **Consumo de Bateria**: Medição do impacto da inferência no dispositivo móvel.
- **Robustez de Oclusão**: Desempenho do modelo quando uma das mãos passa na frente do rosto ou da outra mão.

---

## 3. Estrutura do Model Registry
Todos os modelos exportados devem conter um manifesto em formato JSON que assina digitalmente o artefato. Exemplo:

```json
{
  "model_id": "sinaliza_transformer_v2",
  "version": "2.1.0-rc3",
  "artifact_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "architecture": "TemporalTransformer",
  "dataset_version": "v1.4.0",
  "metrics": {
    "f1_macro": 0.894,
    "top_1_accuracy": 0.912,
    "wer": 0.082,
    "ece": 0.045
  },
  "deployment_parameters": {
    "min_device_ram_gb": 3.0,
    "confidence_threshold": 0.75,
    "hardware_acceleration": "ONNX_NNAPI_TFLITE_GPU"
  },
  "rollback_history": [
    "2.0.4",
    "2.0.2"
  ]
}
```

---

## 4. Critérios de Homologação (Deploy Gates)

Para que um novo modelo seja promovido a produção:
1. **Sem Regressão de Classes**: O modelo não deve performar pior do que a versão anterior em sinais de alta prioridade (ex: "EMERGÊNCIA", "DOR").
2. **Robustez Demográfica**: A disparidade de F1-score entre diferentes tons de pele, gêneros ou destros/canhotos deve ser menor do que 2%.
3. **Assinatura Digital**: O hash do modelo deve ser assinado digitalmente com a chave privada de deploy do servidor. Modelos sem assinatura válida serão recusados pelo aplicativo cliente.
