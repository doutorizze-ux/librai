FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY ml/inference/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml/inference/app.py /app/app.py
COPY ml/inference/preprocessing.py /app/preprocessing.py
COPY ml/models/pilot-v1-core-hands/librai_stgcn.onnx /models/librai_stgcn.onnx
COPY ml/models/pilot-v1-core-hands/model_manifest.json /models/model_manifest.json

EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
