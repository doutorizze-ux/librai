# MotionTCN v1 — piloto assistido de Libras

Este artefato é um classificador experimental para **atendimento de energia
elétrica**. Ele não é um tradutor geral de Libras e não deve ser apresentado
como tal.

## Escopo

- Fonte: [LIBRAS-EQT-UECE](https://doi.org/10.5281/zenodo.20497742)
- Licença do conjunto: CC BY 4.0
- 5.347 vídeos, 5 informantes e 178 classes do conjunto
- 175 textos distintos depois de agrupar três rótulos duplicados
- Entrada: 64 quadros de landmarks de até duas mãos
- Saída: três possibilidades, sempre sujeitas à confirmação da pessoa

As classes são voltadas a solicitações como falta ou oscilação de energia,
religação, consulta e pagamento de faturas. O conjunto não contém vocabulário
geral suficiente para conversação aberta.

## Validação reproduzida

- Treino: informantes 1–4, 4.283 amostras
- Teste signer-independent: informante 5, 1.064 amostras
- Top-1: 78,57%
- Top-3: 92,48%
- Paridade PyTorch/ONNX: diferença máxima absoluta 0,00000381; rankings iguais

Esses números sustentam somente o modo assistido com captura delimitada e
escolha humana entre três opções. Não sustentam tradução contínua automática.

SHA-256 do `model.onnx`:
`daad023e7d484b50b8d6e3963aef859d08601deadebc82791fc77ac3702c07d9`.

## Privacidade e limitações

O aplicativo envia somente landmarks temporais das mãos durante uma captura
visivelmente iniciada pela pessoa. Não envia nem conserva vídeo bruto. A
avaliação disponível cobre apenas um informante externo e ambiente controlado;
distância, iluminação, câmera, variações regionais e pessoas fora do conjunto
podem reduzir a precisão.
