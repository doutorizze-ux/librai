import os
import hashlib
import json
import torch
from train import LibrasTemporalClassifier

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def export_model():
    print("=== Iniciando Exportação para ONNX ===")
    
    # Instanciar modelo com a arquitetura do treinamento
    model = LibrasTemporalClassifier()
    
    weights_path = "ml/models/libras_lstm_weights.pt"
    if os.path.exists(weights_path):
        model.load_state_dict(torch.load(weights_path, map_location=torch.device('cpu')))
        print(f"Pesos do modelo carregados com sucesso de: {weights_path}")
    else:
        print("[Aviso] Pesos de treino não encontrados. Exportando modelo com pesos inicializados aleatoriamente para fins de teste.")
        
    model.eval()
    
    # Criar um input dummy representando (batch_size=1, sequence_length=30, input_dim=63)
    dummy_input = torch.randn(1, 30, 63)
    
    onnx_path = "ml/models/sinaliza_lstm.onnx"
    os.makedirs("ml/models", exist_ok=True)
    
    # Exportar para ONNX
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['input_landmarks'],
        output_names=['output_probabilities'],
        dynamic_axes={
            'input_landmarks': {0: 'batch_size'},
            'output_probabilities': {0: 'batch_size'}
        }
    )
    print(f"Modelo exportado para ONNX com sucesso em: {onnx_path}")
    
    # Calcular Hash SHA-256 do arquivo ONNX gerado
    model_hash = calculate_sha256(onnx_path)
    print(f"Hash SHA-256 do Modelo: {model_hash}")
    
    # Gerar Manifesto do Registro de Modelos
    manifest = {
        "model_id": "sinaliza_lstm_v1",
        "name": "Sinaliza AI LSTM Baseline",
        "version": "1.0.0-lstm",
        "hash_sha256": model_hash,
        "is_active": True,
        "architecture": "LSTM_Temporal",
        "parameters": {
            "input_dim": 63,
            "sequence_length": 30,
            "hidden_dim": 128
        }
    }
    
    manifest_path = "ml/models/model_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"Manifesto do modelo salvo em: {manifest_path}")

if __name__ == "__main__":
    export_model()
