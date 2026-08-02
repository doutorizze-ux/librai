# Proteção dos treinamentos do Librai

## Garantias instaladas

- O PostgreSQL usa um volume persistente independente dos contêineres.
- O serviço `postgres-backup` cria um `pg_dump` verificado antes da API
  iniciar em cada deploy e repete o processo a cada 24 horas.
- Os arquivos locais ficam em um segundo volume, `postgres_backups`, por 30
  dias.
- Um gatilho no PostgreSQL bloqueia qualquer `DELETE` físico da tabela
  `training_samples`. Exclusões funcionais são arquivamentos recuperáveis.
- A API grava uma linha de integridade em cada inicialização e recusa iniciar
  se a quantidade física de amostras cair abaixo do total já conhecido.
- O endpoint `/health` informa quantidades ativas/arquivadas, último backup e
  se a cópia externa foi concluída.

## Variáveis opcionais para cópia externa S3

Configure no Coolify para que cada backup também seja enviado para um storage
S3 compatível. Não grave essas credenciais no Git.

| Variável | Exemplo |
| --- | --- |
| `BACKUP_S3_BUCKET` | `librai-backups` |
| `BACKUP_S3_ENDPOINT` | `https://s3.us-east-1.amazonaws.com` |
| `BACKUP_S3_ACCESS_KEY_ID` | chave fornecida pelo storage |
| `BACKUP_S3_SECRET_ACCESS_KEY` | segredo fornecido pelo storage |
| `BACKUP_S3_REGION` | `us-east-1` |
| `BACKUP_S3_PREFIX` | `librai/postgres` |

Sem `BACKUP_S3_BUCKET`, o backup local continua funcionando e o health check
indica `external_backup: false`.

## Verificação diária

```text
GET https://api.tvcatolica.site/health
```

O estado normal deve mostrar:

```json
{
  "status": "healthy",
  "training_storage": {
    "integrity": "ok",
    "last_backup_at": "data ISO-8601",
    "external_backup": true
  }
}
```

## Restauração

Nunca restaure diretamente sobre a produção sem validar o arquivo. Primeiro
restaure em um banco temporário:

```sh
createdb -h postgres -U sinaliza_user librai_restore_check
pg_restore -h postgres -U sinaliza_user \
  -d librai_restore_check /backups/librai_DATA.dump
psql -h postgres -U sinaliza_user -d librai_restore_check \
  -c "SELECT COUNT(*) FROM training_samples;"
```

Depois da comparação das contagens, a restauração definitiva deve ser feita
em uma janela de manutenção e com um backup adicional do banco atual.
