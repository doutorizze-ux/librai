#!/bin/sh
set -eu

readonly BACKUP_DIR="/backups"
readonly INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
readonly RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
readonly S3_PREFIX="${BACKUP_S3_PREFIX:-librai/postgres}"

export PGHOST="${POSTGRES_HOST:-postgres}"
export PGPORT="${POSTGRES_PORT:-5432}"
export PGUSER="${POSTGRES_USER:?POSTGRES_USER is required}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
export PGDATABASE="${POSTGRES_DB:?POSTGRES_DB is required}"

mkdir -p "$BACKUP_DIR"

wait_for_postgres() {
  until pg_isready -q; do
    sleep 2
  done
}

upload_external_backup() {
  dump_file="$1"
  checksum_file="$2"
  metadata_file="$3"

  if [ -z "${BACKUP_S3_BUCKET:-}" ]; then
    return 1
  fi

  endpoint_args=""
  if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
    endpoint_args="--endpoint-url ${BACKUP_S3_ENDPOINT}"
  fi

  # shellcheck disable=SC2086
  aws s3 cp "$dump_file" "s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}/$(basename "$dump_file")" $endpoint_args || return 1
  # shellcheck disable=SC2086
  aws s3 cp "$checksum_file" "s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}/$(basename "$checksum_file")" $endpoint_args || return 1
  # shellcheck disable=SC2086
  aws s3 cp "$metadata_file" "s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}/$(basename "$metadata_file")" $endpoint_args || return 1
}

create_backup() {
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  name="librai_${timestamp}"
  temporary_dump="${BACKUP_DIR}/.${name}.dump.tmp"
  final_dump="${BACKUP_DIR}/${name}.dump"
  checksum_file="${final_dump}.sha256"
  metadata_file="${final_dump}.meta"

  rm -f "$temporary_dump"
  pg_dump \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    --file="$temporary_dump"
  pg_restore --list "$temporary_dump" >/dev/null
  mv "$temporary_dump" "$final_dump"

  sha256="$(sha256sum "$final_dump" | awk '{print $1}')"
  size_bytes="$(wc -c < "$final_dump" | tr -d ' ')"
  counts="$(psql -Atc "SELECT COUNT(*) FILTER (WHERE deleted_at IS NULL), COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) FROM training_samples")"
  active_count="${counts%%|*}"
  archived_count="${counts##*|}"
  printf '%s  %s\n' "$sha256" "$(basename "$final_dump")" > "$checksum_file"
  printf 'created_at=%s\nactive_samples=%s\narchived_samples=%s\nsize_bytes=%s\n' \
    "$timestamp" "$active_count" "$archived_count" "$size_bytes" > "$metadata_file"

  external_uploaded=false
  if upload_external_backup "$final_dump" "$checksum_file" "$metadata_file"; then
    external_uploaded=true
  fi

  backup_id="$(printf '%s' "$name" | sha256sum | awk '{print $1}')"
  psql -v ON_ERROR_STOP=1 \
    -v backup_id="$backup_id" \
    -v file_name="$(basename "$final_dump")" \
    -v checksum="$sha256" \
    -v size_bytes="$size_bytes" \
    -v active_count="$active_count" \
    -v archived_count="$archived_count" \
    -v external_uploaded="$external_uploaded" <<'SQL'
CREATE TABLE IF NOT EXISTS training_backup_log (
    id VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL,
    active_count BIGINT NOT NULL,
    archived_count BIGINT NOT NULL,
    external_uploaded BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO training_backup_log (
    id,
    created_at,
    file_name,
    sha256,
    size_bytes,
    active_count,
    archived_count,
    external_uploaded
) VALUES (
    :'backup_id',
    CURRENT_TIMESTAMP,
    :'file_name',
    :'checksum',
    :'size_bytes',
    :'active_count',
    :'archived_count',
    :'external_uploaded'
)
ON CONFLICT (id) DO NOTHING;
SQL

  find "$BACKUP_DIR" -type f -mtime "+$RETENTION_DAYS" -delete
  touch /tmp/librai-backup-ready
  printf 'Backup verificado: %s (%s bytes, %s ativos, %s arquivados)\n' \
    "$final_dump" "$size_bytes" "$active_count" "$archived_count"
}

wait_for_postgres
while true; do
  if ! create_backup; then
    rm -f /tmp/librai-backup-ready
    printf 'Falha no backup; nova tentativa em 60 segundos.\n' >&2
    sleep 60
    wait_for_postgres
    continue
  fi
  sleep "$INTERVAL_SECONDS"
done
