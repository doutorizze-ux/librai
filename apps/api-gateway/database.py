import os
from datetime import datetime, timezone

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


def ensure_training_data_guards():
    """Instala proteções persistentes contra perda física dos treinamentos."""
    if engine.dialect.name != "postgresql":
        return

    release = os.getenv("APP_RELEASE", "unknown")[:120]
    integrity_violation = None
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS training_integrity_state (
                id SMALLINT PRIMARY KEY CHECK (id = 1),
                expected_min_total_count BIGINT NOT NULL,
                last_verified_at TIMESTAMPTZ NOT NULL,
                last_release VARCHAR(120) NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS training_integrity_checks (
                id BIGSERIAL PRIMARY KEY,
                checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                release VARCHAR(120) NOT NULL,
                total_count BIGINT NOT NULL,
                active_count BIGINT NOT NULL,
                archived_count BIGINT NOT NULL,
                status VARCHAR(20) NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS training_backup_log (
                id VARCHAR(64) PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                sha256 VARCHAR(64) NOT NULL,
                size_bytes BIGINT NOT NULL,
                active_count BIGINT NOT NULL,
                archived_count BIGINT NOT NULL,
                external_uploaded BOOLEAN NOT NULL DEFAULT FALSE
            )
        """))
        connection.execute(text("""
            CREATE OR REPLACE FUNCTION block_training_samples_hard_delete()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION
                    'Exclusão física de training_samples bloqueada; use arquivamento.';
            END;
            $$
        """))
        connection.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = 'training_samples_no_hard_delete'
                      AND tgrelid = 'training_samples'::regclass
                ) THEN
                    CREATE TRIGGER training_samples_no_hard_delete
                    BEFORE DELETE ON training_samples
                    FOR EACH ROW
                    EXECUTE FUNCTION block_training_samples_hard_delete();
                END IF;
            END;
            $$
        """))

        counts = connection.execute(text("""
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (WHERE deleted_at IS NULL) AS active_count,
                COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) AS archived_count
            FROM training_samples
        """)).mappings().one()
        expected = connection.execute(text("""
            SELECT expected_min_total_count
            FROM training_integrity_state
            WHERE id = 1
        """)).scalar_one_or_none()
        status_value = "ok"
        if expected is not None and counts["total_count"] < expected:
            status_value = "violation"
            integrity_violation = (
                "Integridade dos treinamentos violada: "
                f"esperados ao menos {expected}, encontrados "
                f"{counts['total_count']}."
            )

        connection.execute(text("""
            INSERT INTO training_integrity_checks (
                release,
                total_count,
                active_count,
                archived_count,
                status
            ) VALUES (
                :release,
                :total_count,
                :active_count,
                :archived_count,
                :status
            )
        """), {
            "release": release,
            "total_count": counts["total_count"],
            "active_count": counts["active_count"],
            "archived_count": counts["archived_count"],
            "status": status_value,
        })

        if integrity_violation is None:
            connection.execute(text("""
                INSERT INTO training_integrity_state (
                    id,
                    expected_min_total_count,
                    last_verified_at,
                    last_release
                ) VALUES (1, :total_count, CURRENT_TIMESTAMP, :release)
                ON CONFLICT (id) DO UPDATE SET
                    expected_min_total_count = GREATEST(
                        training_integrity_state.expected_min_total_count,
                        EXCLUDED.expected_min_total_count
                    ),
                    last_verified_at = EXCLUDED.last_verified_at,
                    last_release = EXCLUDED.last_release
            """), {
                "total_count": counts["total_count"],
                "release": release,
            })

    if integrity_violation is not None:
        raise RuntimeError(integrity_violation)


def get_training_integrity_status(db):
    counts = db.execute(text("""
        SELECT
            COUNT(*) AS total_count,
            COUNT(*) FILTER (WHERE deleted_at IS NULL) AS active_count,
            COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) AS archived_count
        FROM training_samples
    """)).mappings().one()
    result = {
        "total_samples": counts["total_count"],
        "active_samples": counts["active_count"],
        "archived_samples": counts["archived_count"],
        "integrity": "ok",
        "last_backup_at": None,
        "external_backup": False,
    }
    if engine.dialect.name != "postgresql":
        return result

    expected = db.execute(text("""
        SELECT expected_min_total_count
        FROM training_integrity_state
        WHERE id = 1
    """)).scalar_one_or_none()
    if expected is not None and counts["total_count"] < expected:
        result["integrity"] = "violation"

    backup = db.execute(text("""
        SELECT created_at, external_uploaded
        FROM training_backup_log
        ORDER BY created_at DESC
        LIMIT 1
    """)).mappings().first()
    if backup:
        created_at = backup["created_at"]
        result["last_backup_at"] = created_at.isoformat()
        result["external_backup"] = backup["external_uploaded"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_hours = (
            datetime.now(timezone.utc) - created_at
        ).total_seconds() / 3600
        if age_hours > 36:
            result["integrity"] = "backup_stale"
    else:
        result["integrity"] = "backup_missing"
    return result

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
