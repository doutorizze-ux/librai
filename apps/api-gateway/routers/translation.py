import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from routers.auth import get_current_user, get_current_user_helper

router = APIRouter(prefix="/v1", tags=["translation"])

import math

def extract_hand_angles(landmarks):
    """Extrai vetor de características de ângulos articulares das mãos (invariante a escala, posição e rotação)."""
    def vec(p1_idx, p2_idx):
        p1, p2 = landmarks[p1_idx], landmarks[p2_idx]
        return [
            p2.get('x', 0.0) - p1.get('x', 0.0),
            p2.get('y', 0.0) - p1.get('y', 0.0),
            p2.get('z', 0.0) - p1.get('z', 0.0)
        ]

    def angle_between(v1, v2):
        dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
        m1 = math.sqrt(v1[0]**2 + v1[1]**2 + v1[2]**2)
        m2 = math.sqrt(v2[0]**2 + v2[1]**2 + v2[2]**2)
        if m1 == 0 or m2 == 0:
            return 0.0
        cos_val = max(-1.0, min(1.0, dot / (m1 * m2)))
        return math.degrees(math.acos(cos_val))

    try:
        angles = [
            angle_between(vec(0, 2), vec(2, 4)),   # Flexão Polegar
            angle_between(vec(0, 5), vec(5, 8)),   # Flexão Indicador
            angle_between(vec(0, 9), vec(9, 12)),  # Flexão Médio
            angle_between(vec(0, 13), vec(13, 16)),# Flexão Anelar
            angle_between(vec(0, 17), vec(17, 20)),# Flexão Mínimo
            angle_between(vec(5, 8), vec(9, 12)),  # Abertura Indicador-Médio
            angle_between(vec(9, 12), vec(13, 16)),# Abertura Médio-Anelar
            angle_between(vec(13, 16), vec(17, 20))# Abertura Anelar-Mínimo
        ]
        return angles
    except Exception:
        return None

@router.post("/translation/predict")
def predict_sign(
    payload: dict,
    db: Session = Depends(get_db)
):
    input_landmarks = payload.get("landmarks")
    if not input_landmarks or len(input_landmarks) != 21:
        return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}
    
    input_angles = extract_hand_angles(input_landmarks)
    if not input_angles:
        return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}
    
    # 2. Carregar amostras de treino gravadas pelos profissionais
    samples = db.query(models.TrainingSample).all()
    if not samples:
        return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}
    
    best_label = "SINAL_DESCONHECIDO"
    min_dist = 999.0
    
    # 3. K-Nearest Neighbors (KNN) de Vetores Angulares Articulares
    for sample in samples:
        db_points = sample.landmarks
        if not db_points or len(db_points) < 21:
            continue
            
        num_frames = len(db_points) // 21
        for f in range(num_frames):
            frame_points = db_points[f*21 : (f+1)*21]
            if len(frame_points) != 21:
                continue
                
            try:
                db_angles = extract_hand_angles(frame_points)
                if not db_angles:
                    continue
                
                # Distância euclidiana no espaço vetorial de ângulos (em graus)
                dist = math.sqrt(sum((a - b)**2 for a, b in zip(input_angles, db_angles)))
                
                if dist < min_dist:
                    min_dist = dist
                    best_label = sample.sign_name
            except Exception:
                continue
                
    # Limiar em graus: 30.0 graus de diferença total permitida no espaço angular
    threshold = 30.0
    if min_dist < threshold:
        confidence = float(max(0.5, 1.0 - (min_dist / threshold) * 0.5))
        return {"label": best_label, "confidence": round(confidence, 2)}
        
    return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}

@router.post("/translation/sessions", response_model=schemas.SessionResponse)
def create_session(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    session = models.TranslationSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.get("/translation/sessions/{id}", response_model=schemas.SessionResponse)
def get_session(id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    session = db.query(models.TranslationSession).filter(models.TranslationSession.id == id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão de tradução não encontrada")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    return session

@router.post("/translation/sessions/{id}/segments", response_model=schemas.SegmentResponse)
def add_segment(id: str, segment: schemas.SegmentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    session = db.query(models.TranslationSession).filter(models.TranslationSession.id == id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    
    db_segment = models.TranslationSegment(
        session_id=id,
        text_detected=segment.text_detected,
        confidence=segment.confidence,
        raw_landmarks_ref=segment.raw_landmarks_ref
    )
    db.add(db_segment)
    db.commit()
    db.refresh(db_segment)
    return db_segment

@router.post("/translation/sessions/{id}/finish", response_model=schemas.SessionResponse)
def finish_session(id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    session = db.query(models.TranslationSession).filter(models.TranslationSession.id == id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    
    session.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session

@router.post("/translation/segments/{id}/corrections", response_model=schemas.CorrectionResponse)
def add_correction(id: str, correction: schemas.CorrectionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    segment = db.query(models.TranslationSegment).filter(models.TranslationSegment.id == id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segmento de tradução não encontrado")
    
    db_correction = models.TranslationCorrection(
        segment_id=id,
        corrected_text=correction.corrected_text,
        reviewer_id=current_user.id
    )
    db.add(db_correction)
    db.commit()
    db.refresh(db_correction)
    return db_correction

# --- WEBSOCKET FOR REAL-TIME TRANSLATION ---
@router.websocket("/translation/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    
    # Autenticação via query token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token ausente")
        return
    
    try:
        current_user = get_current_user_helper(token, db)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Não autorizado")
        return

    # Iniciar sessão de tradução automática do WebSocket
    session = models.TranslationSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        while True:
            # Receber landmarks compactados
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Verificação de controle de fluxo / ping-pong
            if message.get("type") == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
                continue
            
            # Validação de dados de landmarks
            landmarks = message.get("landmarks")
            if not landmarks:
                await websocket.send_text(json.dumps({
                    "type": "ERROR",
                    "code": "MISSING_LANDMARKS",
                    "message": "Nenhum landmark recebido no frame"
                }))
                continue

            # MOCK PIPELINE - Em produção, repassa para inference-service
            # Para testes determinísticos, simulamos respostas com base no conteúdo
            text_detected = "Olá"
            confidence = 0.92
            
            # Persistir segmento
            segment = models.TranslationSegment(
                session_id=session.id,
                text_detected=text_detected,
                confidence=confidence
            )
            db.add(segment)
            db.commit()

            await websocket.send_text(json.dumps({
                "type": "WS_PARTIAL_RESULT",
                "segment_id": segment.id,
                "text": text_detected,
                "confidence": confidence,
                "model_version": "test-v1"
            }))
            
    except WebSocketDisconnect:
        session.finished_at = datetime.utcnow()
        db.commit()
