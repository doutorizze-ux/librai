import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sinaliza_dev.db")

# Ajuste do SQLite para permitir concorrência no desenvolvimento local
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_training_sample_columns():
    """Migração aditiva segura para instalações existentes sem Alembic."""
    inspector = inspect(engine)
    if "training_samples" not in inspector.get_table_names():
        return

    existing = {
        column["name"]
        for column in inspector.get_columns("training_samples")
    }
    column_definitions = {
        "trainer_name": "VARCHAR",
        "frame_count": "INTEGER",
        "deleted_at": "TIMESTAMP",
        "deleted_by": "VARCHAR",
    }
    with engine.begin() as connection:
        for column_name, column_type in column_definitions.items():
            if column_name not in existing:
                connection.execute(
                    text(
                        f"ALTER TABLE training_samples "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
