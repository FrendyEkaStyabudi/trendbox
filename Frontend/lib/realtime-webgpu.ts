type OrtModule = typeof import("onnxruntime-web");
type OrtSession = import("onnxruntime-web").InferenceSession;

export type DetectionKind = "face" | "head" | "clothing";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ObjectDetection {
  box: BoundingBox;
  label: string;
  confidence: number;
  kind: DetectionKind;
}

export interface TrackedPerson {
  id: number;
  emotion: string;
  confidence: number;
  head: string;
  clothes: string;
  duration: number;
  box: BoundingBox;
}

export interface CompletedDetection {
  track_id: number;
  emotion: string | null;
  emotion_confidence: number;
  head: string | null;
  head_confidence: number;
  clothing: string | null;
  clothing_confidence: number;
  duration: number;
}

export interface BrowserInferenceConfig {
  emotion: boolean;
  head: boolean;
  clothing: boolean;
}

export interface BrowserInferenceResult {
  people: TrackedPerson[];
  heads: ObjectDetection[];
  clothing: ObjectDetection[];
  completed: CompletedDetection[];
  processingMs: number;
  fps: number;
  provider: "webgpu" | "wasm";
  mode: "full" | "lite" | "face-only";
}

interface TrackState {
  id: number;
  firstSeen: number;
  lastSeen: number;
  emotionHistory: Array<{ label: string; confidence: number }>;
  head: ObjectDetection | null;
  clothing: ObjectDetection | null;
}

interface LetterboxTransform {
  sourceWidth: number;
  sourceHeight: number;
  scale: number;
  padX: number;
  padY: number;
}

const MODEL_SIZE = 416;
const MODEL_BASE_URL = (
  process.env.NEXT_PUBLIC_MODEL_BASE_URL || "/models"
).replace(/\/$/, "");
const modelUrl = (filename: string) => `${MODEL_BASE_URL}/${filename}`;
const YOLO_INTERVAL = 5;
const YOLO_CONFIDENCE = 0.35;
const NMS_IOU = 0.45;
const TRACK_TTL_MS = 3000;
const MAX_FACES = 6;

const isMemoryError = (error: unknown) =>
  /memory|out of bounds|allocation|device lost/i.test(
    error instanceof Error ? error.message : String(error)
  );

const disposeTensors = (tensors: Record<string, import("onnxruntime-web").Tensor>) => {
  for (const tensor of Object.values(tensors)) tensor.dispose();
};

const EMOTION_LABELS = [
  "angry",
  "disgusted",
  "fearful",
  "happy",
  "neutral",
  "sad",
  "surprised",
];
const DISPLAY_EMOTIONS = new Set(["angry", "fear", "happy", "sad", "surprised"]);

const HEAD_LABELS = ["hijab", "rambut", "topi"];
const HEAD_TRANSLATIONS: Record<string, string> = {
  hijab: "hijab",
  rambut: "hair",
  topi: "hat",
};

const CLOTHING_LABELS = [
  "celana panjang",
  "celana pendek",
  "gaun",
  "hijab",
  "kaos",
  "kemeja",
  "outer",
  "rok",
  "sweater",
  "tas",
  "topi",
];
const CLOTHING_TRANSLATIONS: Record<string, string> = {
  "celana panjang": "long_pants",
  "celana pendek": "shorts",
  gaun: "dress",
  hijab: "hijab",
  kaos: "t-shirt",
  kemeja: "shirt",
  outer: "outer",
  rok: "skirt",
  sweater: "sweater",
  tas: "bag",
  topi: "hat",
};
const ALLOWED_CLOTHING = new Set([
  "sweater",
  "shorts",
  "skirt",
  "long_pants",
  "t-shirt",
  "shirt",
  "blouse",
  "outer",
]);

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const boxIou = (a: BoundingBox, b: BoundingBox) => {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top);
  const union = a.width * a.height + b.width * b.height - intersection;
  return union > 0 ? intersection / union : 0;
};

const nonMaximumSuppression = (detections: ObjectDetection[]) => {
  const pending = [...detections].sort((a, b) => b.confidence - a.confidence);
  const kept: ObjectDetection[] = [];

  while (pending.length > 0 && kept.length < 30) {
    const best = pending.shift()!;
    kept.push(best);
    for (let index = pending.length - 1; index >= 0; index -= 1) {
      if (
        pending[index].label === best.label &&
        boxIou(pending[index].box, best.box) >= NMS_IOU
      ) {
        pending.splice(index, 1);
      }
    }
  }

  return kept;
};

export class BrowserInferenceEngine {
  private ort!: OrtModule;
  private headSession?: OrtSession;
  private clothingSession?: OrtSession;
  private emotionSession?: OrtSession;
  private faceDetector: any;
  private provider: "webgpu" | "wasm" = "wasm";
  private mode: "full" | "lite" | "face-only" = "face-only";
  private modelCanvas: HTMLCanvasElement;
  private emotionCanvas: HTMLCanvasElement;
  private frameCount = 0;
  private cachedHeads: ObjectDetection[] = [];
  private cachedClothing: ObjectDetection[] = [];
  private tracks = new Map<number, TrackState>();
  private nextTrackId = 1;

  private constructor() {
    this.modelCanvas = document.createElement("canvas");
    this.modelCanvas.width = MODEL_SIZE;
    this.modelCanvas.height = MODEL_SIZE;
    this.emotionCanvas = document.createElement("canvas");
    this.emotionCanvas.width = 48;
    this.emotionCanvas.height = 48;
  }

  static async create(onProgress?: (message: string) => void) {
    const engine = new BrowserInferenceEngine();
    await engine.initialize(onProgress);
    return engine;
  }

  get executionProvider() {
    return this.provider;
  }

  get executionMode() {
    return this.mode;
  }

  get capabilities() {
    return {
      emotion: Boolean(this.emotionSession),
      head: Boolean(this.headSession),
      clothing: Boolean(this.clothingSession),
    };
  }

  private async releaseSession(session?: OrtSession) {
    if (session) await session.release();
  }

  private async disableYoloModels() {
    const head = this.headSession;
    const clothing = this.clothingSession;
    this.headSession = undefined;
    this.clothingSession = undefined;
    this.cachedHeads = [];
    this.cachedClothing = [];
    await Promise.allSettled([this.releaseSession(head), this.releaseSession(clothing)]);
    this.mode = this.emotionSession ? "lite" : "face-only";
  }

  private async disableEmotionModel() {
    const emotion = this.emotionSession;
    this.emotionSession = undefined;
    await this.releaseSession(emotion);
    this.mode = "face-only";
  }

  async recoverFromMemoryPressure() {
    if (this.headSession || this.clothingSession) {
      await this.disableYoloModels();
      return "Light mode enabled: face and emotion detection will continue.";
    }
    if (this.emotionSession) {
      await this.disableEmotionModel();
      return "Memory-saving mode enabled: only face bounding boxes will run.";
    }
    return "This device does not have enough memory for browser inference.";
  }

  private async initialize(onProgress?: (message: string) => void) {
    onProgress?.("Loading ONNX Runtime...");
    this.ort = (await import("onnxruntime-web/webgpu")) as unknown as OrtModule;
    this.ort.env.wasm.wasmPaths = "/ort/";
    this.ort.env.wasm.numThreads = 1;
    this.ort.env.wasm.proxy = false;

    const hasWebGpu = typeof navigator !== "undefined" && "gpu" in navigator;
    const deviceMemory = Number((navigator as Navigator & { deviceMemory?: number }).deviceMemory || 0);
    const lowMemoryDevice = deviceMemory > 0 && deviceMemory <= 4;
    const sessionOptions = (provider: "webgpu" | "wasm") => ({
      // Do not mix WebGPU and WASM in one session. A mixed fallback keeps two
      // large memory arenas alive and is the main cause of mobile OOM crashes.
      executionProviders: [provider],
      graphOptimizationLevel: "all",
    }) as any;

    onProgress?.(
      hasWebGpu ? "Preparing models on the device GPU..." : "WebGPU is unavailable, preparing the CPU fallback..."
    );

    if (hasWebGpu) {
      try {
        // Sessions are deliberately created sequentially. Parallel creation of
        // the three models can temporarily require more than twice the memory.
        onProgress?.("Loading the emotion model...");
        this.emotionSession = await this.ort.InferenceSession.create(
          modelUrl("model_emotion2.onnx"),
          sessionOptions("webgpu")
        );
        this.provider = "webgpu";
        this.mode = "lite";

        if (!lowMemoryDevice) {
          try {
            onProgress?.("Loading the head model...");
            this.headSession = await this.ort.InferenceSession.create(
              modelUrl("kepala.onnx"),
              sessionOptions("webgpu")
            );
            onProgress?.("Loading the clothing model...");
            this.clothingSession = await this.ort.InferenceSession.create(
              modelUrl("pakaian.onnx"),
              sessionOptions("webgpu")
            );
            this.mode = "full";
          } catch (error) {
            console.warn("Full WebGPU models exceed device capacity; using lite mode.", error);
            await this.disableYoloModels();
            onProgress?.("Device memory is limited; light mode has been enabled...");
          }
        } else {
          onProgress?.("This is a low-memory device; light mode has been enabled...");
        }
      } catch (error) {
        console.warn("WebGPU initialization failed; using memory-safe WASM mode.", error);
        await this.disableYoloModels();
        await this.disableEmotionModel();
      }
    }

    if (!this.emotionSession) {
      this.provider = "wasm";
      this.mode = "face-only";
      onProgress?.("Preparing lightweight CPU mode...");
      try {
        this.emotionSession = await this.ort.InferenceSession.create(
          modelUrl("model_emotion2.onnx"),
          sessionOptions("wasm")
        );
        this.mode = "lite";
      } catch (error) {
        console.warn("Emotion WASM model could not fit in memory; using face-only mode.", error);
        this.emotionSession = undefined;
        this.mode = "face-only";
      }
    }

    onProgress?.("Loading the face detector...");
    const { FaceDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
    const vision = await FilesetResolver.forVisionTasks("/mediapipe");
    const faceOptions = (delegate: "GPU" | "CPU") => ({
      baseOptions: {
        modelAssetPath: modelUrl("blaze_face_short_range.tflite"),
        delegate,
      },
      runningMode: "VIDEO" as const,
      minDetectionConfidence: 0.5,
      minSuppressionThreshold: 0.3,
    });

    try {
      this.faceDetector = await FaceDetector.createFromOptions(vision, faceOptions("GPU"));
    } catch (error) {
      console.warn("MediaPipe GPU delegate failed; using CPU delegate.", error);
      this.faceDetector = await FaceDetector.createFromOptions(vision, faceOptions("CPU"));
    }

    onProgress?.(`Model siap (${this.provider.toUpperCase()} / ${this.mode}).`);
  }

  private createYoloTensor(video: HTMLVideoElement) {
    const sourceWidth = video.videoWidth;
    const sourceHeight = video.videoHeight;
    const scale = Math.min(MODEL_SIZE / sourceWidth, MODEL_SIZE / sourceHeight);
    const drawWidth = Math.round(sourceWidth * scale);
    const drawHeight = Math.round(sourceHeight * scale);
    const padX = Math.floor((MODEL_SIZE - drawWidth) / 2);
    const padY = Math.floor((MODEL_SIZE - drawHeight) / 2);
    const context = this.modelCanvas.getContext("2d", { willReadFrequently: true });
    if (!context) throw new Error("The preprocessing canvas is unavailable.");

    context.fillStyle = "rgb(114, 114, 114)";
    context.fillRect(0, 0, MODEL_SIZE, MODEL_SIZE);
    context.drawImage(video, 0, 0, sourceWidth, sourceHeight, padX, padY, drawWidth, drawHeight);

    const pixels = context.getImageData(0, 0, MODEL_SIZE, MODEL_SIZE).data;
    const planeSize = MODEL_SIZE * MODEL_SIZE;
    const input = new Float32Array(planeSize * 3);
    for (let index = 0; index < planeSize; index += 1) {
      const pixelIndex = index * 4;
      input[index] = pixels[pixelIndex] / 255;
      input[planeSize + index] = pixels[pixelIndex + 1] / 255;
      input[planeSize * 2 + index] = pixels[pixelIndex + 2] / 255;
    }

    return {
      tensor: new this.ort.Tensor("float32", input, [1, 3, MODEL_SIZE, MODEL_SIZE]),
      transform: { sourceWidth, sourceHeight, scale, padX, padY } satisfies LetterboxTransform,
    };
  }

  private parseYolo(
    output: import("onnxruntime-web").Tensor,
    classLabels: string[],
    translations: Record<string, string>,
    kind: "head" | "clothing",
    transform: LetterboxTransform
  ) {
    const dimensions = output.dims.map(Number);
    const channels = dimensions[1];
    const candidates = dimensions[2];
    const values = output.data as Float32Array;
    const detections: ObjectDetection[] = [];

    for (let candidate = 0; candidate < candidates; candidate += 1) {
      let classIndex = -1;
      let confidence = 0;
      for (let index = 0; index < classLabels.length; index += 1) {
        const score = Number(values[(4 + index) * candidates + candidate]);
        if (score > confidence) {
          confidence = score;
          classIndex = index;
        }
      }
      if (confidence < YOLO_CONFIDENCE || classIndex < 0) continue;

      const translated = translations[classLabels[classIndex]];
      if (!translated || (kind === "clothing" && !ALLOWED_CLOTHING.has(translated))) continue;

      const centerX = Number(values[candidate]);
      const centerY = Number(values[candidates + candidate]);
      const width = Number(values[candidates * 2 + candidate]);
      const height = Number(values[candidates * 3 + candidate]);
      const left = (centerX - width / 2 - transform.padX) / transform.scale;
      const top = (centerY - height / 2 - transform.padY) / transform.scale;
      const right = (centerX + width / 2 - transform.padX) / transform.scale;
      const bottom = (centerY + height / 2 - transform.padY) / transform.scale;
      const x = clamp(left, 0, transform.sourceWidth);
      const y = clamp(top, 0, transform.sourceHeight);
      const x2 = clamp(right, 0, transform.sourceWidth);
      const y2 = clamp(bottom, 0, transform.sourceHeight);
      if (x2 - x < 4 || y2 - y < 4) continue;

      detections.push({
        box: { x, y, width: x2 - x, height: y2 - y },
        label: translated,
        confidence,
        kind,
      });
    }

    // Segmentation models append mask channels after their class scores. The
    // parser intentionally reads only 4 + class count and ignores the masks.
    if (channels < 4 + classLabels.length) {
      throw new Error(`Invalid YOLO output: ${dimensions.join("x")}`);
    }
    return nonMaximumSuppression(detections);
  }

  private detectFaces(video: HTMLVideoElement, now: number) {
    const result = this.faceDetector.detectForVideo(video, now);
    return (result.detections || [])
      .slice(0, MAX_FACES)
      .map((detection: any): ObjectDetection | null => {
        const box = detection.boundingBox;
        if (!box) return null;
        const x = clamp(Number(box.originX), 0, video.videoWidth);
        const y = clamp(Number(box.originY), 0, video.videoHeight);
        const right = clamp(Number(box.originX + box.width), 0, video.videoWidth);
        const bottom = clamp(Number(box.originY + box.height), 0, video.videoHeight);
        if (right - x < 10 || bottom - y < 10) return null;
        return {
          box: { x, y, width: right - x, height: bottom - y },
          label: "face",
          confidence: Number(detection.categories?.[0]?.score || 0),
          kind: "face",
        };
      })
      .filter((value: ObjectDetection | null): value is ObjectDetection => value !== null);
  }

  private async classifyEmotion(video: HTMLVideoElement, box: BoundingBox) {
    const session = this.emotionSession;
    if (!session) return null;
    const context = this.emotionCanvas.getContext("2d", { willReadFrequently: true });
    if (!context) throw new Error("The emotion canvas is unavailable.");
    context.drawImage(video, box.x, box.y, box.width, box.height, 0, 0, 48, 48);
    const pixels = context.getImageData(0, 0, 48, 48).data;
    const grayscale = new Float32Array(48 * 48);
    for (let index = 0; index < grayscale.length; index += 1) {
      const pixelIndex = index * 4;
      grayscale[index] =
        (0.299 * pixels[pixelIndex] +
          0.587 * pixels[pixelIndex + 1] +
          0.114 * pixels[pixelIndex + 2]) /
        255;
    }

    const inputName = session.inputNames[0];
    const outputName = session.outputNames[0];
    const tensor = new this.ort.Tensor("float32", grayscale, [1, 48, 48, 1]);
    let output: Record<string, import("onnxruntime-web").Tensor> | undefined;
    try {
      output = await session.run({ [inputName]: tensor });
      const scores = output[outputName].data as Float32Array;
      let bestIndex = 0;
      for (let index = 1; index < scores.length; index += 1) {
        if (Number(scores[index]) > Number(scores[bestIndex])) bestIndex = index;
      }

      let label = EMOTION_LABELS[bestIndex];
      const confidence = Number(scores[bestIndex]);
      if (label === "sad" && confidence < 0.4) label = "neutral";
      if (label === "fearful") label = "fear";
      return { label, confidence };
    } finally {
      tensor.dispose();
      if (output) disposeTensors(output);
    }
  }

  private findTrack(box: BoundingBox, usedTrackIds: Set<number>, now: number) {
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    let best: TrackState | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    const threshold = Math.max(80, Math.max(box.width, box.height) * 1.5);

    for (const track of this.tracks.values()) {
      if (usedTrackIds.has(track.id) || now - track.lastSeen > TRACK_TTL_MS) continue;
      const latest = (track as TrackState & { lastBox?: BoundingBox }).lastBox;
      if (!latest) continue;
      const trackX = latest.x + latest.width / 2;
      const trackY = latest.y + latest.height / 2;
      const distance = Math.hypot(centerX - trackX, centerY - trackY);
      if (distance < threshold && distance < bestDistance) {
        best = track;
        bestDistance = distance;
      }
    }

    if (!best) {
      best = {
        id: this.nextTrackId++,
        firstSeen: now,
        lastSeen: now,
        emotionHistory: [],
        head: null,
        clothing: null,
      };
      this.tracks.set(best.id, best);
    }
    (best as TrackState & { lastBox?: BoundingBox }).lastBox = box;
    best.lastSeen = now;
    usedTrackIds.add(best.id);
    return best;
  }

  private dominantEmotion(track: TrackState) {
    const grouped = new Map<string, number[]>();
    for (const item of track.emotionHistory) {
      if (!DISPLAY_EMOTIONS.has(item.label)) continue;
      const scores = grouped.get(item.label) || [];
      scores.push(item.confidence);
      grouped.set(item.label, scores);
    }

    let label = "-";
    let count = 0;
    let confidence = 0;
    for (const [candidate, scores] of grouped.entries()) {
      if (scores.length > count) {
        label = candidate;
        count = scores.length;
        confidence = scores.reduce((sum, score) => sum + score, 0) / scores.length;
      }
    }
    return { label, confidence };
  }

  private completeTrack(track: TrackState, now: number): CompletedDetection {
    const emotion = this.dominantEmotion(track);
    return {
      track_id: track.id,
      emotion: emotion.label === "-" ? null : emotion.label,
      emotion_confidence: emotion.confidence,
      head: track.head?.label || null,
      head_confidence: track.head?.confidence || 0,
      clothing: track.clothing?.label || null,
      clothing_confidence: track.clothing?.confidence || 0,
      duration: Math.max(0, (now - track.firstSeen) / 1000),
    };
  }

  async infer(video: HTMLVideoElement, config: BrowserInferenceConfig): Promise<BrowserInferenceResult> {
    const startedAt = performance.now();
    const now = performance.now();
    this.frameCount += 1;

    if (!config.head) this.cachedHeads = [];
    if (!config.clothing) this.cachedClothing = [];

    if (
      (this.headSession || this.clothingSession) &&
      (this.frameCount === 1 || this.frameCount % YOLO_INTERVAL === 0)
    ) {
      const { tensor, transform } = this.createYoloTensor(video);
      try {
        // Run the large models sequentially and immediately dispose every
        // output tensor. Keeping outputs from previous frames leaks GPU/WASM
        // memory until the runtime eventually throws "memory access out of bounds".
        if (config.head && this.headSession) {
          const session = this.headSession;
          const outputs = await session.run({ [session.inputNames[0]]: tensor });
          try {
            this.cachedHeads = this.parseYolo(
              outputs[session.outputNames[0]],
              HEAD_LABELS,
              HEAD_TRANSLATIONS,
              "head",
              transform
            );
          } finally {
            disposeTensors(outputs);
          }
        }
        if (config.clothing && this.clothingSession) {
          const session = this.clothingSession;
          const outputs = await session.run({ [session.inputNames[0]]: tensor });
          try {
            this.cachedClothing = this.parseYolo(
              outputs[session.outputNames[0]],
              CLOTHING_LABELS,
              CLOTHING_TRANSLATIONS,
              "clothing",
              transform
            );
          } finally {
            disposeTensors(outputs);
          }
        }
      } catch (error) {
        if (!isMemoryError(error)) throw error;
        console.warn("YOLO inference exceeded device memory; switching to lite mode.", error);
        await this.disableYoloModels();
      } finally {
        tensor.dispose();
      }
    }

    const faces = this.detectFaces(video, now);
    const usedTrackIds = new Set<number>();
    const people: TrackedPerson[] = [];

    for (const face of faces) {
      const track = this.findTrack(face.box, usedTrackIds, now);
      if (config.emotion && this.emotionSession) {
        try {
          const emotion = await this.classifyEmotion(video, face.box);
          if (emotion) {
            track.emotionHistory.push(emotion);
            if (track.emotionHistory.length > 30) track.emotionHistory.shift();
          }
        } catch (error) {
          if (!isMemoryError(error)) throw error;
          console.warn("Emotion inference exceeded device memory; switching to face-only mode.", error);
          await this.disableEmotionModel();
        }
      }

      if (config.head) {
        track.head =
          this.cachedHeads
            .filter((item) => boxIou(face.box, item.box) > 0)
            .sort((a, b) => b.confidence - a.confidence)[0] || track.head;
      } else {
        track.head = null;
      }

      if (config.clothing) {
        const faceCenterX = face.box.x + face.box.width / 2;
        const faceCenterY = face.box.y + face.box.height / 2;
        track.clothing =
          this.cachedClothing
            .filter((item) => {
              const itemCenterX = item.box.x + item.box.width / 2;
              const itemCenterY = item.box.y + item.box.height / 2;
              return itemCenterY > faceCenterY && Math.abs(itemCenterX - faceCenterX) < face.box.width * 1.5;
            })
            .sort((a, b) => a.box.y - b.box.y)[0] || track.clothing;
      } else {
        track.clothing = null;
      }

      const dominant = config.emotion ? this.dominantEmotion(track) : { label: "-", confidence: 0 };
      people.push({
        id: track.id,
        emotion: dominant.label,
        confidence: dominant.confidence,
        head: track.head?.label || "-",
        clothes: track.clothing?.label || "-",
        duration: Math.max(0, (now - track.firstSeen) / 1000),
        box: face.box,
      });
    }

    const completed: CompletedDetection[] = [];
    for (const track of [...this.tracks.values()]) {
      if (now - track.lastSeen > TRACK_TTL_MS) {
        completed.push(this.completeTrack(track, now));
        this.tracks.delete(track.id);
      }
    }

    const processingMs = performance.now() - startedAt;
    return {
      people,
      heads: this.cachedHeads,
      clothing: this.cachedClothing,
      completed,
      processingMs,
      fps: processingMs > 0 ? 1000 / processingMs : 0,
      provider: this.provider,
      mode: this.mode,
    };
  }

  flushTracks() {
    const now = performance.now();
    const completed = [...this.tracks.values()].map((track) => this.completeTrack(track, now));
    this.tracks.clear();
    return completed;
  }

  async dispose() {
    this.faceDetector?.close?.();
    await Promise.allSettled(
      [this.headSession, this.clothingSession, this.emotionSession]
        .filter((session): session is OrtSession => Boolean(session))
        .map((session) => session.release())
    );
  }
}

export function drawInferenceOverlay(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  result: BrowserInferenceResult
) {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) return;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, width, height);
  context.font = "600 15px system-ui";
  context.lineWidth = 2;

  const drawDetection = (detection: ObjectDetection, color: string) => {
    const { x, y, width: boxWidth, height: boxHeight } = detection.box;
    context.strokeStyle = color;
    context.strokeRect(x, y, boxWidth, boxHeight);
    context.fillStyle = color;
    context.fillText(
      `${detection.label} ${(detection.confidence * 100).toFixed(0)}%`,
      x,
      Math.max(16, y - 5)
    );
  };

  result.heads.forEach((item) => drawDetection(item, "#ef4444"));
  result.clothing.forEach((item) => drawDetection(item, "#facc15"));
  for (const person of result.people) {
    context.strokeStyle = "#22c55e";
    context.lineWidth = 3;
    context.strokeRect(person.box.x, person.box.y, person.box.width, person.box.height);
    context.fillStyle = "#22c55e";
    context.fillText(
      `ID:${person.id} ${person.emotion}`,
      person.box.x,
      Math.max(16, person.box.y - 22)
    );
  }

  context.fillStyle = "rgba(0, 0, 0, 0.72)";
  context.fillRect(8, 8, 330, 30);
  context.fillStyle = "#4ade80";
  context.fillText(
    `Face:${result.people.length} Head:${result.heads.length} Clothes:${result.clothing.length} ${result.provider.toUpperCase()}`,
    16,
    29
  );
}
