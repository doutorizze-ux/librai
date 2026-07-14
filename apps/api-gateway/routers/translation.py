import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from routers.auth import get_current_user, get_current_user_helper

router = APIRouter(prefix="/v1", tags=["translation"])

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
