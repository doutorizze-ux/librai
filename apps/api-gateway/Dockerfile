# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final image
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/api-gateway/ /app/
COPY data/vlibras/catalog-v1.json /data/vlibras/catalog-v1.json
COPY data/vlibras/LICENSE-GPL-3.0.txt /data/vlibras/LICENSE-GPL-3.0.txt
ADD --checksum=sha256:14348391e42eac0fbc8036b9952d0fc1ff786d850029eab17af2a10cef7331d9 https://github.com/doutorizze-ux/librai/releases/download/vlibras-landmarks-v1/vlibras-landmarks-v1.tar /tmp/vlibras-landmarks-v1.tar
RUN mkdir -p /data/vlibras/reference-motions \
    && tar -xf /tmp/vlibras-landmarks-v1.tar -C /data/vlibras/reference-motions \
    && rm /tmp/vlibras-landmarks-v1.tar
COPY data/vlibras/reference-motions/ /data/vlibras/reference-motions/

ENV VLIBRAS_CATALOG_PATH=/data/vlibras/catalog-v1.json
ENV VLIBRAS_MOTION_PATH=/data/vlibras/reference-motions

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
