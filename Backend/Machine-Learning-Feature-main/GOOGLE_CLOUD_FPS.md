# Google Cloud FPS tuning

The realtime pipeline is tuned through environment variables, so the same image
can run on CPU or GPU infrastructure.

## Recommended CPU baseline

Start with 4 vCPU and 8 GiB RAM, one Gunicorn worker, and low request concurrency
(1-4 active camera sessions per instance). Use these defaults:

```text
INFERENCE_WIDTH=416
YOLO_IMGSZ=416
YOLO_INTERVAL=5
MIN_FRAME_INTERVAL=0.08
TFLITE_THREADS=4
OMP_NUM_THREADS=4
INFERENCE_CONCURRENCY=1
OUTPUT_JPEG_QUALITY=55
RTSP_MAX_WIDTH=640
```

If CPU is saturated, raise `YOLO_INTERVAL` to 8 or lower `YOLO_IMGSZ` and
`INFERENCE_WIDTH` to 320. If CPU has headroom, lower `YOLO_INTERVAL` to 3.

## NVIDIA GPU service (GCE/GKE or Cloud Run GPU)

The container must use a CUDA-compatible PyTorch base/dependency set. Then set:

```text
YOLO_DEVICE=0
YOLO_HALF=true
YOLO_IMGSZ=416
YOLO_INTERVAL=2
MIN_FRAME_INTERVAL=0.04
```

Do not configure multiple Gunicorn workers with the current in-memory session
design: each worker would load its own models and consume GPU/RAM independently.
Scale horizontally instead.

## Frontend build variables

```text
NEXT_PUBLIC_INFERENCE_WIDTH=416
NEXT_PUBLIC_INFERENCE_HEIGHT=312
NEXT_PUBLIC_FRAME_INTERVAL_MS=90
NEXT_PUBLIC_JPEG_QUALITY=0.55
```

The browser now sends JPEG frames as Socket.IO binary and waits for the previous
result before sending another frame. This prevents queue buildup and keeps the
display on the newest available frame.
