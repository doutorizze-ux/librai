import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, Float, JSON
from sqlalchemy.orm import relationship
from database import Base

# Tabela de Associação User-Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    consents = relationship("Consent", back_populates="user")
    sessions = relationship("TranslationSession", back_populates="user")

class Role(Base):
    __tablename__ = "roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    permissions = Column(JSON, nullable=True) # Ex: ["admin", "models:deploy", "audit:view"]

    users = relationship("User", secondary=user_roles, back_populates="roles")

class Consent(Base):
    __tablename__ = "consents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(String, nullable=False) # Ex: "camera_usage", "data_contribution"
    version = Column(String, nullable=False)
    accepted = Column(Boolean, default=False)
    signed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="consents")

class TranslationSession(Base):
    __tablename__ = "translation_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")
    segments = relationship("TranslationSegment", back_populates="session")

class TranslationSegment(Base):
    __tablename__ = "translation_segments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("translation_sessions.id", ondelete="CASCADE"), nullable=False)
    raw_landmarks_ref = Column(String, nullable=True) # Caminho S3 se o consentimento B for ativo
    text_detected = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TranslationSession", back_populates="segments")
    corrections = relationship("TranslationCorrection", back_populates="segment")

class TranslationCorrection(Base):
    __tablename__ = "translation_corrections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id = Column(String, ForeignKey("translation_segments.id", ondelete="CASCADE"), nullable=False)
    corrected_text = Column(String, nullable=False)
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    segment = relationship("TranslationSegment", back_populates="corrections")

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)

    signs = relationship("Sign", back_populates="category")

class Sign(Base):
    __tablename__ = "signs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category_id = Column(String, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    regionality = Column(String, nullable=True)
    usage_context = Column(String, nullable=True)

    category = relationship("Category", back_populates="signs")

class Model(Base):
    __tablename__ = "models"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    version = Column(String, unique=True, nullable=False)
    hash_sha256 = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    deployed_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True) # Mantido mesmo se o usuário for deletado (histórico comercial)
    action = Column(String, nullable=False) # Ex: "DEPLOY_MODEL", "EDIT_SIGN"
    target = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
