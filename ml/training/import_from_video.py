import os
import json
import cv2
import mediapipe as mp

# Inicializar soluções do MediaPipe
mp_hands = mp.solutions.hands
mp_pose = mp.solutions.pose

def extract_landmarks_from_video(video_path: str, output_json_path: str):
    """
    Lê um arquivo de vídeo (ex: baixado do YouTube), extrai as coordenadas geométricas
    dos landmarks a cada frame usando o MediaPipe e salva em um arquivo JSON de treino.
    """
    print(f"=== Processando vídeo: {os.path.basename(video_path)} ===")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[Erro] Não foi possível abrir o vídeo: {video_path}")
        return False

    all_frames_landmarks = []

    # Configurar rastreadores de mãos e corpo
    with mp_hands.Hands(static_image_mode=False, max_num_hands=2, min_detection_confidence=0.5) as hands, \
         mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5) as pose:
         
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break # Fim do vídeo

            # Converter cor BGR (OpenCV) para RGB (MediaPipe)
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Executar detecção
            hands_results = hands.process(image_rgb)
            
            frame_points = []
            
            # Se detectou mãos, extrai as coordenadas X, Y, Z
            if hands_results.multi_hand_landmarks:
                for hand_landmarks in hands_results.multi_hand_landmarks:
                    for lm in hand_landmarks.landmark:
                        frame_points.append({
                            'x': round(lm.x, 4),
                            'y': round(lm.y, 4),
                            'z': round(lm.z, 4)
                        })
            
            # Salvar apenas se detectou dados suficientes no frame para evitar arquivos vazios
            if frame_points:
                all_frames_landmarks.append(frame_points)

    cap.release()
    
    # Salvar a sequência temporal em formato JSON de treino
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_frames_landmarks, f, indent=2)
        
    print(f"[Sucesso] Extração concluída. Salvo em: {output_json_path}")
    print(f"  - Total de frames com movimento capturados: {len(all_frames_landmarks)}")
    return True

if __name__ == "__main__":
    # Exemplo de Uso:
    # 1. Baixe um vídeo do youtube contendo o sinal "obrigado".
    # 2. Salve o arquivo como "video_obrigado.mp4" na raiz do projeto.
    # 3. Defina os caminhos abaixo e execute:
    #    python import_from_video.py
    
    video_exemplo = "video_obrigado.mp4"
    saida_treino = "ml/dataset/participante_youtube/obrigado_01.json"
    
    if os.path.exists(video_exemplo):
        extract_landmarks_from_video(video_exemplo, saida_treino)
    else:
        print(f"\n[Dica] Para usar o script:")
        print(f"1. Coloque um arquivo de vídeo chamado '{video_exemplo}' na raiz do projeto.")
        print(f"2. Execute o script: python ml/training/import_from_video.py")
        print(f"Ele converterá o vídeo automaticamente em coordenadas JSON para o seu banco de dados!\n")
