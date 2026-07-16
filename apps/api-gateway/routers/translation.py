import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from routers.auth import get_current_user, get_current_user_helper

router = APIRouter(prefix="/v1", tags=["translation"])

@router.post("/translation/predict")
def predict_sign(
    payload: dict,
    db: Session = Depends(get_db)
):
    input_landmarks = payload.get("landmarks")
    if not input_landmarks or len(input_landmarks) != 21:
        return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}
    
    # 1. Normalizar input em relação ao pulso e escala do tamanho da mão (pontos 0 a 9)
    try:
        wrist_in = input_landmarks[0]
        mcp_in = input_landmarks[9]
        dx_scale = mcp_in.get("x", 0.0) - wrist_in.get("x", 0.0)
        dy_scale = mcp_in.get("y", 0.0) - wrist_in.get("y", 0.0)
        dz_scale = mcp_in.get("z", 0.0) - wrist_in.get("z", 0.0)
        scale_in = (dx_scale**2 + dy_scale**2 + dz_scale**2) ** 0.5
        if scale_in == 0:
            scale_in = 1.0

        norm_input = []
        for p in input_landmarks:
            norm_input.append({
                "x": (p.get("x", 0.0) - wrist_in.get("x", 0.0)) / scale_in,
                "y": (p.get("y", 0.0) - wrist_in.get("y", 0.0)) / scale_in,
                "z": (p.get("z", 0.0) - wrist_in.get("z", 0.0)) / scale_in,
            })
    except Exception as e:
        return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}
    
    # 2. Carregar amostras de treino gravadas pelos profissionais
    samples = db.query(models.TrainingSample).all()
    if not samples:
        return {"label": "SINAL_DESCONHECIDO", "confidence": 0.0}
    
    best_label = "SINAL_DESCONHECIDO"
    min_dist = 999.0
    
    # 3. K-Nearest Neighbors (KNN) com invariância de escala e translação
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
                wrist_db = frame_points[0]
                mcp_db = frame_points[9]
                dx_db_scale = mcp_db.get("x", 0.0) - wrist_db.get("x", 0.0)
                dy_db_scale = mcp_db.get("y", 0.0) - wrist_db.get("y", 0.0)
                dz_db_scale = mcp_db.get("z", 0.0) - wrist_db.get("z", 0.0)
                scale_db = (dx_db_scale**2 + dy_db_scale**2 + dz_db_scale**2) ** 0.5
                if scale_db == 0:
                    scale_db = 1.0

                dist = 0.0
                for i in range(21):
                    val_in_x = norm_input[i]["x"]
                    val_in_y = norm_input[i]["y"]
                    val_in_z = norm_input[i]["z"]

                    val_db_x = (frame_points[i].get("x", 0.0) - wrist_db.get("x", 0.0)) / scale_db
                    val_db_y = (frame_points[i].get("y", 0.0) - wrist_db.get("y", 0.0)) / scale_db
                    val_db_z = (frame_points[i].get("z", 0.0) - wrist_db.get("z", 0.0)) / scale_db

                    dx = val_in_x - val_db_x
                    dy = val_in_y - val_db_y
                    dz = val_in_z - val_db_z
                    dist += (dx * dx + dy * dy + dz * dz)
                
                if dist < min_dist:
                    min_dist = dist
                    best_label = sample.sign_name
            except Exception:
                continue
                
    # Limiar preciso para vetor normalizado de translação + escala
    threshold = 0.40
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
