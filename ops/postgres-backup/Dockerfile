FROM postgres:15-alpine

RUN apk add --no-cache aws-cli tzdata

COPY ops/postgres-backup/backup.sh /usr/local/bin/librai-backup
RUN chmod 0555 /usr/local/bin/librai-backup

ENTRYPOINT ["/usr/local/bin/librai-backup"]
