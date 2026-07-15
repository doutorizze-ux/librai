from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, translation, dictionary, models as model_router, privacy, admin, training

# Inicializar Tabelas do Banco de Dados local (SQLite)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sinaliza AI API Gateway",
    description="Serviço principal de APIs e tradução em tempo real para o Sinaliza AI",
    version="1.0.0"
)

import os
from fastapi import Request

# Configuração de CORS Dinâmico para Produção
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de Segurança para Hardening de Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Registrar Roteadores
app.include_router(auth.router)
app.include_router(translation.router)
app.include_router(dictionary.router)
app.include_router(model_router.router)
app.include_router(privacy.router)
app.include_router(admin.router)
app.include_router(training.router)

@app.get("/")
def read_root():
    return {
        "app": "Sinaliza AI API Gateway",
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
