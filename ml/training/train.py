import os
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

# --- 1. DEFINIÇÃO DA ARQUITETURA TEMPORAL (LSTM BASELINE) ---
class LibrasTemporalClassifier(nn.Module):
    """
    Modelo temporal LSTM para classificação de sinais isolados de Libras a partir de landmarks.
    Entrada: Sequência de frames (ex: 30 frames) contendo landmarks (ex: 21 pontos x 3 eixos = 63 dimensões).
    """
    def __init__(self, input_dim=63, hidden_dim=128, num_classes=5, num_layers=2):
        super(LibrasTemporalClassifier, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_dim, num_classes)
        
    def forward(self, x):
        # x shape: (batch_size, sequence_length, input_dim)
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
        
        out, _ = self.lstm(x, (h0, c0))
        # Seleciona o output do último passo temporal (Sequence Classification)
        out = out[:, -1, :]
        out = self.fc(out)
        return out

# --- 2. DATASET E GOVERNANÇA (SEPARAÇÃO POR PARTICIPANTE) ---
class LibrasLandmarksDataset(Dataset):
    """
    Simulador de carregamento de Landmarks para o treino.
    Seguindo o regulamento de DATASET_GOVERNANCE.md, a separação de treino/teste
    é feita por ID de PARTICIPANTE e nunca misturando amostras do mesmo participante.
    """
    def __init__(self, participants, num_samples_per_part=50, seq_len=30, input_dim=63):
        self.data = []
        self.labels = []
        
        # Simulação de geração de dados sintéticos por participante
        for part_id in participants:
            for _ in range(num_samples_per_part):
                # Landmarks simulados: X, Y, Z com pequeno ruído aleatório
                features = torch.randn(seq_len, input_dim)
                # Classes de 0 a 4 (ex: AJUDA, SAÚDE, BOM_DIA, OBRIGADO, OUTROS)
                label = torch.randint(0, 5, (1,)).item()
                self.data.append(features)
                self.labels.append(label)
                
    def __len__(self):
        return len(self.data)
        
    def __getitem__(self, idx):
        return self.data[idx], self.labels[idx]

def run_training():
    print("=== Iniciando Pipeline de Treinamento - Sinaliza AI ===")
    
    # Mapeamento de participantes (Divisão por ID de participante)
    train_participants = ["p_001", "p_002", "p_003", "p_004", "p_005", "p_006"]
    val_participants = ["p_007", "p_008"] # Participantes não vistos no conjunto de treino
    
    train_dataset = LibrasLandmarksDataset(train_participants)
    val_dataset = LibrasLandmarksDataset(val_participants)
    
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
    
    # Inicialização do modelo, otimizador e critério de perda
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LibrasTemporalClassifier().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Loop de Treino Rápido (Demonstrativo/Executável)
    epochs = 3
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * inputs.size(0)
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
            
        train_acc = 100.0 * correct / total
        epoch_loss = train_loss / total
        
        # Validação
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                val_loss += loss.item() * inputs.size(0)
                _, predicted = outputs.max(1)
                val_total += targets.size(0)
                val_correct += predicted.eq(targets).sum().item()
                
        val_acc = 100.0 * val_correct / val_total
        print(f"Epoch {epoch+1}/{epochs} | Loss: {epoch_loss:.4f} | Acc Treino: {train_acc:.1f}% | Acc Validação: {val_acc:.1f}%")
        
    # Salvar pesos locais
    os.makedirs("ml/models", exist_ok=True)
    torch.save(model.state_dict(), "ml/models/libras_lstm_weights.pt")
    print("Treinamento finalizado. Pesos salvos em: ml/models/libras_lstm_weights.pt")

if __name__ == "__main__":
    run_training()
