import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

import database


POSTGRES_TEST_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="TEST_POSTGRES_URL não configurada",
)
def test_postgres_blocks_hard_delete_and_detects_missing_samples():
    test_engine = create_engine(POSTGRES_TEST_URL)
    original_engine = database.engine
    database.engine = test_engine
    try:
        with test_engine.begin() as connection:
            connection.execute(text(
                "DROP TABLE IF EXISTS training_integrity_checks CASCADE"
            ))
            connection.execute(text(
                "DROP TABLE IF EXISTS training_integrity_state CASCADE"
            ))
            connection.execute(text(
                "DROP TABLE IF EXISTS training_backup_log CASCADE"
            ))
            connection.execute(text(
                "DROP TABLE IF EXISTS training_samples CASCADE"
            ))
            connection.execute(text("""
                CREATE TABLE training_samples (
                    id VARCHAR PRIMARY KEY,
                    deleted_at TIMESTAMP NULL
                )
            """))
            connection.execute(text("""
                INSERT INTO training_samples (id, deleted_at)
                VALUES ('amostra-segura', NULL)
            """))

        database.ensure_training_data_guards()

        with pytest.raises(DBAPIError):
            with test_engine.begin() as connection:
                connection.execute(text(
                    "DELETE FROM training_samples WHERE id='amostra-segura'"
                ))

        with test_engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE training_samples DISABLE TRIGGER "
                "training_samples_no_hard_delete"
            ))
            connection.execute(text(
                "DELETE FROM training_samples WHERE id='amostra-segura'"
            ))
            connection.execute(text(
                "ALTER TABLE training_samples ENABLE TRIGGER "
                "training_samples_no_hard_delete"
            ))

        with pytest.raises(RuntimeError, match="Integridade dos treinamentos"):
            database.ensure_training_data_guards()
    finally:
        with test_engine.begin() as connection:
            connection.execute(text(
                "DROP TABLE IF EXISTS training_integrity_checks CASCADE"
            ))
            connection.execute(text(
                "DROP TABLE IF EXISTS training_integrity_state CASCADE"
            ))
            connection.execute(text(
                "DROP TABLE IF EXISTS training_backup_log CASCADE"
            ))
            connection.execute(text(
                "DROP TABLE IF EXISTS training_samples CASCADE"
            ))
            connection.execute(text(
                "DROP FUNCTION IF EXISTS "
                "block_training_samples_hard_delete() CASCADE"
            ))
        database.engine = original_engine
        test_engine.dispose()
