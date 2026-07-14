# Guia Prático de Treinamento - Sinaliza AI

Este guia explica como você fará o treinamento de novos sinais físicos de Libras quando trouxer uma pessoa que conheça a língua de sinais para gravar os movimentos.

---

## Passo 1: Gravando os Sinais (Coleta de Dados)

1. Peça para a pessoa que sabe Libras se sentar em frente à câmera do computador ou celular.
2. Ela deve fazer o mesmo sinal (ex: **SAÚDE**) de **30 a 50 vezes**.
3. **Instruções para a gravação:**
   * Ela deve iniciar com as mãos paradas (posição neutra).
   * Fazer o movimento do sinal de forma clara e natural.
   * Voltar as mãos para a posição inicial.
   * Aguardar 1 segundo e repetir o sinal.
4. O próprio sistema de câmera do aplicativo vai extrair as coordenadas da mão (os pontos de articulação) e salvará arquivos de dados (tabelas em formato JSON ou CSV).

---

## Passo 2: Onde colocar os arquivos salvos

No seu computador, vá até a pasta do projeto `librai` e crie a pasta do seu banco de dados de treino:
`librai/ml/dataset/`

Organize os arquivos divididos por pasta de participante para respeitar a LGPD e evitar que a IA decore as características físicas da pessoa:
*   `librai/ml/dataset/joao/bom_dia_01.json` (gravações do João)
*   `librai/ml/dataset/joao/ajuda_01.json`
*   `librai/ml/dataset/maria/bom_dia_01.json` (gravações da Maria)
*   `librai/ml/dataset/maria/ajuda_01.json`

---

## Passo 3: Rodando o Treinamento (Apenas 2 comandos)

Quando os arquivos estiverem organizados, abra o terminal do Windows na pasta do projeto e execute os passos abaixo:

### 1. Instalar o PyTorch (A biblioteca de IA)
Digite este comando no terminal para instalar a ferramenta de Inteligência Artificial no seu computador:
```bash
c:\Users\mauricio\Desktop\librai\apps\api-gateway\venv\Scripts\pip install torch onnx
```

### 2. Rodar o Treinamento
Com a biblioteca instalada, digite o comando para a Inteligência Artificial começar a aprender a ler as coordenadas dos arquivos que você salvou:
```bash
c:\Users\mauricio\Desktop\librai\apps\api-gateway\venv\Scripts\python ml/training/train.py
```
*A tela começará a mostrar o aprendizado da IA: "Epoch 1, Loss: 0.8... Epoch 2, Loss: 0.2... Acurácia: 97%"*

---

## Passo 4: Exportar o Modelo para o Aplicativo (Último comando)

Para finalizar, digite o comando que transforma o cérebro treinado em um arquivo superleve (`sinaliza_lstm.onnx`) compatível com celulares e navegadores Web:
```bash
c:\Users\mauricio\Desktop\librai\apps\api-gateway\venv\Scripts\python ml/training/export.py
```

### O que fazer com o arquivo gerado?
O script salvará o arquivo final em `ml/models/sinaliza_lstm.onnx`. Basta enviar este arquivo para o seu servidor web ou colocá-lo na pasta de arquivos do seu aplicativo Flutter! O app fará a leitura da câmera física em tempo real usando esse arquivo.
