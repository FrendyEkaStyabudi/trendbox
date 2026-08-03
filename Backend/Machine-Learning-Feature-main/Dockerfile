# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11-slim

EXPOSE 8080

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# OpenCV/Ultralytics runtime libraries and predictable CPU thread defaults.
ENV OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    TFLITE_THREADS=4 \
    INFERENCE_WIDTH=416 \
    YOLO_IMGSZ=416 \
    YOLO_INTERVAL=5 \
    INFERENCE_CONCURRENCY=1 \
    MIN_FRAME_INTERVAL=0.08

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Install pip requirements
COPY requirements-cloudrun.txt .
RUN python -m pip install --no-cache-dir \
      torch==2.5.1 torchvision==0.20.1 \
      --index-url https://download.pytorch.org/whl/cu121 && \
    python -m pip install --no-cache-dir -r requirements-cloudrun.txt

WORKDIR /app
COPY app.py apisql.py ./
COPY model_emotion2.tflite kepala.pt pakaian.pt ./

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
# One worker is required because sessions live in process memory. Threads keep
# Socket.IO responsive while inference runs; scale with more Cloud instances.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 0 app:app"]
