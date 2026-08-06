"use client";

import { useEffect, useRef, useState } from "react";
import {
  BrowserInferenceEngine,
  CompletedDetection,
  drawInferenceOverlay,
} from "@/lib/realtime-webgpu";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Cpu,
  Loader2,
  Network,
  PlayCircle,
  Settings,
  StopCircle,
  Video,
} from "lucide-react";

const DASHBOARD_API_URL =
  process.env.NEXT_PUBLIC_DASHBOARD_API_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "https://trendbox-dashboard-api-590242083739.asia-southeast2.run.app";
const FRAME_INTERVAL_MS = Number(process.env.NEXT_PUBLIC_WEBGPU_FRAME_INTERVAL_MS ?? 180);
const DEFAULT_REALTIME_API_URL =
  process.env.NEXT_PUBLIC_REALTIME_API_URL ||
  "https://trendbox-realtime-api-590242083739.asia-southeast2.run.app";

type TrackingConfig = {
  emotion: boolean;
  head: boolean;
  clothing: boolean;
  db_save: boolean;
};

type TrackingMode = "browser" | "device-api";

type RealtimeLog = {
  timestamp: string;
  level: "info" | "warn" | "error" | "debug";
  message: string;
};

export default function RealtimeTrackingPage() {
  const [isTrackingActive, setIsTrackingActive] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [trackingMode, setTrackingMode] = useState<TrackingMode>("device-api");
  const [deviceApiUrl, setDeviceApiUrl] = useState(DEFAULT_REALTIME_API_URL);
  const [deviceFeedUrl, setDeviceFeedUrl] = useState("");
  const [cameraError, setCameraError] = useState("");
  const [modelStatus, setModelStatus] = useState("Model not loaded yet");
  const [provider, setProvider] = useState<"webgpu" | "wasm" | null>(null);
  const [inferenceMode, setInferenceMode] = useState<"full" | "lite" | "face-only" | null>(null);
  const [capabilities, setCapabilities] = useState({ emotion: true, head: true, clothing: true });
  const [processingMs, setProcessingMs] = useState(0);
  const [trackingData, setTrackingData] = useState<any[]>([]);
  const [realtimeLogs, setRealtimeLogs] = useState<RealtimeLog[]>([]);
  const [config, setConfig] = useState<TrackingConfig>({
    emotion: true,
    head: true,
    clothing: true,
    db_save: true,
  });

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const engineRef = useRef<BrowserInferenceEngine | null>(null);
  const frameTimerRef = useRef<number | null>(null);
  const deviceStatusTimerRef = useRef<number | null>(null);
  const runningRef = useRef(false);
  const configRef = useRef(config);
  const frameCounterRef = useRef(0);
  const memoryRecoveryRef = useRef(0);
  const inferenceModeRef = useRef<"full" | "lite" | "face-only" | null>(null);
  const sessionIdRef = useRef("");

  const appendLog = (
    level: RealtimeLog["level"],
    message: string
  ) => {
    const entry: RealtimeLog = {
      timestamp: new Date().toLocaleTimeString("id-ID", { hour12: false }),
      level,
      message,
    };
    setRealtimeLogs((previous) => [...previous.slice(-79), entry]);
  };

  const normalizeApiUrl = (value: string) => {
    const trimmed = value.trim().replace(/\/+$/, "");
    if (!trimmed) throw new Error("Enter the Jetson or Raspberry Pi API URL first.");
    const parsed = new URL(trimmed);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      throw new Error("The device API URL must start with http:// or https://.");
    }
    return parsed.toString().replace(/\/+$/, "");
  };

  const parseConfidence = (value: unknown) => {
    if (typeof value === "number") return value > 1 ? value / 100 : value;
    if (typeof value === "string") {
      const parsed = Number(value.replace("%", "").trim());
      return Number.isFinite(parsed) ? parsed / 100 : 0;
    }
    return 0;
  };

  const normalizeTrackedPeople = (people: any[] = []) =>
    people.map((person) => ({
      id: person.id ?? person.track_id ?? "-",
      emotion: person.emotion ?? "-",
      confidence: parseConfidence(person.confidence ?? person.emotion_confidence),
      head: person.head ?? person.head_label ?? "-",
      clothes: person.clothes ?? person.clothing ?? person.clothing_label ?? "-",
      duration: Number(person.duration ?? 0),
    }));

  const [cameraOptions, setCameraOptions] = useState<{ id: string; name: string; type: "jetson" | "browser" }[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");

  useEffect(() => {
    let isMounted = true;
    const jetsonUrl = process.env.NEXT_PUBLIC_REALTIME_API_URL || DEFAULT_REALTIME_API_URL;

    const detectAvailableCameras = async () => {
      const options: { id: string; name: string; type: "jetson" | "browser" }[] = [];

      // Check Jetson / Device API availability
      try {
        const res = await fetch(`${jetsonUrl}/health`, { cache: "no-store" });
        if (res.ok) {
          options.push({
            id: "jetson-device-api",
            name: "📷 Jetson Nano Camera (Realtime AI API)",
            type: "jetson",
          });
        }
      } catch {
        // Jetson offline: automatically omitted from camera dropdown
      }

      // Check local browser cameras
      try {
        if (typeof navigator !== "undefined" && navigator.mediaDevices?.enumerateDevices) {
          const devices = await navigator.mediaDevices.enumerateDevices();
          const videoDevices = devices.filter((d) => d.kind === "videoinput");
          videoDevices.forEach((dev, idx) => {
            options.push({
              id: dev.deviceId || `local-cam-${idx}`,
              name: dev.label || `📹 Camera ${idx + 1} (Browser)`,
              type: "browser",
            });
          });
        }
      } catch {
        // Ignore webcam permission errors
      }

      if (options.length === 0) {
        options.push({
          id: "default-webcam",
          name: "📹 Web Camera",
          type: "browser",
        });
      }

      if (isMounted) {
        setCameraOptions(options);

        setSelectedCameraId((current) => {
          if (current && options.some((o) => o.id === current)) return current;
          const jetsonOpt = options.find((o) => o.type === "jetson");
          return jetsonOpt ? jetsonOpt.id : options[0].id;
        });
      }
    };

    void detectAvailableCameras();
    const interval = setInterval(detectAvailableCameras, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const storedUrl = window.localStorage.getItem("trendbox-realtime-api-url");
    const activeUrl = storedUrl || process.env.NEXT_PUBLIC_REALTIME_API_URL || DEFAULT_REALTIME_API_URL;
    setDeviceApiUrl(activeUrl);
  }, []);

  useEffect(() => {
    configRef.current = config;
  }, [config]);

  const persistRecords = async (records: CompletedDetection[]) => {
    if (!configRef.current.db_save || records.length === 0) return;

    try {
      const response = await fetch(`${DASHBOARD_API_URL}/api/realtime/detections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          records,
        }),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(`HTTP ${response.status}: ${message.slice(0, 160)}`);
      }
      const body = await response.json();
      const inserted = body.inserted || {};
      appendLog(
        "info",
        `Database saved: emotion=${inserted.emotion || 0}, head=${inserted.head || 0}, clothing=${inserted.clothing || 0}`
      );
    } catch (error: any) {
      console.error("Failed to persist WebGPU detections:", error);
      appendLog("error", `Failed to save to the database: ${error?.message || "unknown error"}`);
    }
  };

  const stopCamera = () => {
    runningRef.current = false;
    if (frameTimerRef.current !== null) {
      window.clearTimeout(frameTimerRef.current);
      frameTimerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    const canvas = overlayCanvasRef.current;
    canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  };

  const stopBrowserTracking = () => {
    stopCamera();
    const engine = engineRef.current;
    engineRef.current = null;
    const completed = engine?.flushTracks(configRef.current) || [];
    void persistRecords(completed);
    void engine?.dispose();
    setIsTrackingActive(false);
    setIsStarting(false);
    setTrackingData([]);
    appendLog("info", "Tracking stopped.");
  };

  const stopDeviceTracking = () => {
    if (deviceStatusTimerRef.current !== null) {
      window.clearInterval(deviceStatusTimerRef.current);
      deviceStatusTimerRef.current = null;
    }
    setDeviceFeedUrl("");
    setIsTrackingActive(false);
    setIsStarting(false);
    setTrackingData([]);
    setProcessingMs(0);
    appendLog("info", "Device API tracking stopped.");
  };

  const stopTracking = () => {
    if (trackingMode === "device-api") {
      stopDeviceTracking();
      return;
    }
    stopBrowserTracking();
  };

  const scheduleInference = () => {
    const runFrame = async () => {
      if (!runningRef.current) return;
      const video = videoRef.current;
      const canvas = overlayCanvasRef.current;
      const engine = engineRef.current;

      if (
        document.visibilityState === "visible" &&
        video &&
        canvas &&
        engine &&
        video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA
      ) {
        try {
          const result = await engine.infer(video, configRef.current);
          if (!runningRef.current) return;
          drawInferenceOverlay(canvas, video, result);
          setTrackingData(result.people);
          setProcessingMs(result.processingMs);
          setProvider(result.provider);
          if (result.mode !== inferenceModeRef.current) {
            inferenceModeRef.current = result.mode;
            setInferenceMode(result.mode);
            const available = engine.capabilities;
            setCapabilities(available);
            setConfig((current) => {
              const next = {
                ...current,
                emotion: current.emotion && available.emotion,
                head: current.head && available.head,
                clothing: current.clothing && available.clothing,
              };
              configRef.current = next;
              return next;
            });
          }
          if (result.completed.length > 0) void persistRecords(result.completed);

          frameCounterRef.current += 1;
          if (frameCounterRef.current % 20 === 0) {
            appendLog(
              "debug",
              `${result.provider.toUpperCase()} ${result.processingMs.toFixed(0)} ms · ${result.people.length} faces`
            );
          }
        } catch (error: any) {
          console.error("Browser inference failed:", error);
          const message = error?.message || "unknown error";
          if (/memory|out of bounds|allocation|device lost/i.test(message)) {
            memoryRecoveryRef.current += 1;
            if (memoryRecoveryRef.current <= 2) {
              const recoveryMessage = await engine.recoverFromMemoryPressure();
              const available = engine.capabilities;
              setCapabilities(available);
              setInferenceMode(engine.executionMode);
              inferenceModeRef.current = engine.executionMode;
              setConfig((current) => {
                const next = {
                  ...current,
                  emotion: current.emotion && available.emotion,
                  head: current.head && available.head,
                  clothing: current.clothing && available.clothing,
                };
                configRef.current = next;
                return next;
              });
              setModelStatus(recoveryMessage);
              appendLog("warn", recoveryMessage);
            } else {
              setCameraError("This device does not have enough memory. Tracking was stopped safely.");
              appendLog("error", "Tracking was stopped to prevent the browser from running out of memory.");
              stopBrowserTracking();
            }
          } else {
            appendLog("error", `Inference failed: ${message}`);
          }
        }
      }

      if (runningRef.current) {
        frameTimerRef.current = window.setTimeout(runFrame, FRAME_INTERVAL_MS);
      }
    };

    void runFrame();
  };

  const pollDeviceStatus = (baseUrl: string) => {
    let lastLoggedStatus: boolean | null = null;
    const loadStatus = async () => {
      try {
        const response = await fetch(`${baseUrl}/status`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = await response.json();
        const rawPeople = normalizeTrackedPeople(body.tracked_people ?? body.people ?? []);
        const people = rawPeople.map((person) => ({
          ...person,
          emotion: configRef.current.emotion ? person.emotion : "-",
          confidence: configRef.current.emotion ? person.confidence : 0,
          head: configRef.current.head ? person.head : "-",
          clothes: configRef.current.clothing ? person.clothes : "-",
        }));
        setTrackingData(people);
        setProcessingMs(Number(body.processing_ms ?? 0));

        const isJetsonConnected = Boolean(body.jetson_connected);
        if (isJetsonConnected !== lastLoggedStatus) {
          lastLoggedStatus = isJetsonConnected;
          if (isJetsonConnected) {
            appendLog("info", "🟢 Jetson Nano terhubung & aktif mengirimkan data stream!");
          } else {
            appendLog("warn", "🟡 ML Backend aktif, tetapi belum ada stream dari Jetson Nano (Jalankan python3 jetson_rtsp.py di Jetson).");
          }
        }

        setModelStatus(
          isJetsonConnected
            ? `Jetson Nano Terhubung: ${body.people_count ?? people.length} orang terdeteksi`
            : "Realtime ML API Siap: Menunggu stream kamera Jetson Nano..."
        );
      } catch (error: any) {
        appendLog("warn", `Unable to read device status: ${error?.message || "unknown error"}`);
      }
    };

    void loadStatus();
    deviceStatusTimerRef.current = window.setInterval(loadStatus, 2000);
  };

  const sendConfigToDeviceApi = async (newConfig: TrackingConfig, baseUrlOverride?: string) => {
    try {
      const url = baseUrlOverride || deviceApiUrl || DEFAULT_REALTIME_API_URL;
      const baseUrl = normalizeApiUrl(url);
      const res = await fetch(`${baseUrl}/update_config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newConfig),
      });
      if (res.ok) {
        appendLog("info", `Setting deteksi diperbarui ke Jetson API (${baseUrl})`);
      } else {
        appendLog(
          "warn",
          `Jetson API (${baseUrl}) belum diperbarui (HTTP ${res.status}). Harap salin file app.py & apisql.py terbaru ke perangkat Jetson Nano lalu restart service.`
        );
      }
    } catch (err: any) {
      // Offline / network error ignored silently or logged
    }
  };

  const startDeviceTracking = async (overrideUrl?: string) => {
    if (isStarting || isTrackingActive) return;
    setCameraError("");
    setRealtimeLogs([]);
    setTrackingData([]);
    setProcessingMs(0);
    setIsStarting(true);

    try {
      const baseUrl = normalizeApiUrl(overrideUrl || deviceApiUrl || DEFAULT_REALTIME_API_URL);
      window.localStorage.setItem("trendbox-realtime-api-url", baseUrl);
      void sendConfigToDeviceApi(configRef.current, baseUrl);

      if (window.location.protocol === "https:" && baseUrl.startsWith("http://")) {
        appendLog(
          "warn",
          "This page is HTTPS while the device API is HTTP. Some browsers may block local HTTP device access."
        );
      }

      appendLog("info", `Connecting to device API at ${baseUrl}...`);
      try {
        const response = await fetch(`${baseUrl}/health`, { cache: "no-store" });
        if (response.ok) {
          const body = await response.json();
          appendLog("info", `Device API health check passed: ${body.service || "ready"}`);
        } else {
          appendLog("warn", `Health endpoint returned HTTP ${response.status}; trying stream and status anyway.`);
        }
      } catch {
        appendLog("warn", "Health endpoint is unavailable; trying stream and status anyway.");
      }

      setDeviceFeedUrl(`${baseUrl}/video_feed?ts=${Date.now()}`);
      setProvider(null);
      setInferenceMode(null);
      setModelStatus("Device API connected. Waiting for camera stream...");
      setIsTrackingActive(true);
      setIsStarting(false);
      pollDeviceStatus(baseUrl);
    } catch (error: any) {
      setIsStarting(false);
      setIsTrackingActive(false);
      const message = error?.message || "Unable to connect to the device API.";
      setCameraError(message);
      appendLog("error", message);
    }
  };

  const startBrowserTracking = async () => {
    if (isStarting || isTrackingActive) return;
    setCameraError("");
    setRealtimeLogs([]);
    setTrackingData([]);
    setProcessingMs(0);
    setIsStarting(true);
    memoryRecoveryRef.current = 0;
    frameCounterRef.current = 0;
    sessionIdRef.current =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `browser-${Date.now()}`;

    try {
      if (!window.isSecureContext) {
        throw new Error("Camera access and WebGPU require HTTPS or localhost.");
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support camera access.");
      }

      // Give React one frame to mount the video element shown during startup.
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      appendLog("info", "Requesting camera permission...");
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
        audio: false,
      });
      streamRef.current = stream;
      if (!videoRef.current) throw new Error("The camera element is not ready.");
      videoRef.current.srcObject = stream;
      await videoRef.current.play();

      if (!engineRef.current) {
        engineRef.current = await BrowserInferenceEngine.create((message) => {
          setModelStatus(message);
          appendLog("info", message);
        });
      }

      const executionProvider = engineRef.current.executionProvider;
      const executionMode = engineRef.current.executionMode;
      const available = engineRef.current.capabilities;
      setProvider(executionProvider);
      setInferenceMode(executionMode);
      inferenceModeRef.current = executionMode;
      setCapabilities(available);
      setConfig((current) => {
        const next = {
          ...current,
          emotion: current.emotion && available.emotion,
          head: current.head && available.head,
          clothing: current.clothing && available.clothing,
        };
        configRef.current = next;
        return next;
      });
      setModelStatus(
        executionMode === "full"
          ? "Full mode is ready on the device GPU"
          : executionMode === "lite"
            ? "Light mode is ready: face and emotion detection"
            : "Memory-saving mode is ready: face bounding boxes"
      );
      appendLog(
        executionProvider === "webgpu" ? "info" : "warn",
        executionProvider === "webgpu"
          ? `WebGPU is active (${executionMode}). Camera frames are processed on this device.`
          : `Browser CPU mode is active (${executionMode}). Large models are disabled to protect memory.`
      );

      runningRef.current = true;
      setIsTrackingActive(true);
      setIsStarting(false);
      scheduleInference();
    } catch (error: any) {
      console.error("Failed to start browser tracking:", error);
      stopCamera();
      setIsStarting(false);
      setIsTrackingActive(false);
      const message = error?.message || "Unable to start the camera and models.";
      setCameraError(message);
      appendLog("error", message);
    }
  };

  const startTracking = async () => {
    if (trackingMode === "device-api") {
      await startDeviceTracking();
      return;
    }
    await startBrowserTracking();
  };

  useEffect(() => {
    return () => {
      runningRef.current = false;
      if (frameTimerRef.current !== null) window.clearTimeout(frameTimerRef.current);
      if (deviceStatusTimerRef.current !== null) window.clearInterval(deviceStatusTimerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const completed = engineRef.current?.flushTracks(configRef.current) || [];
      if (completed.length > 0) void persistRecords(completed);
      void engineRef.current?.dispose();
      engineRef.current = null;
    };
  }, []);

  const toggleConfig = (key: keyof TrackingConfig) => {
    setConfig((current) => {
      const next = { ...current, [key]: !current[key] };
      configRef.current = next;
      void sendConfigToDeviceApi(next);
      return next;
    });
  };

  return (
    <div className="w-full max-w-full overflow-x-hidden bg-white">
      <div className="mx-auto w-full max-w-[1400px] space-y-6">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold">
            <Video className="h-7 w-7 text-purple-600" />
            <span className="min-w-0">Real-time Emotion Tracking</span>
          </h1>
          <p className="mt-2 text-gray-600">
            Run tracking in this browser, or connect to a Jetson/Raspberry Pi realtime API.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="space-y-6">
            <Card className="rounded-2xl border">
              <CardHeader>
                <CardTitle>Realtime Tracking</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="camera-select" className="font-semibold text-slate-700">
                    Pilih Kamera / Sumber Stream
                  </Label>
                  <select
                    id="camera-select"
                    value={selectedCameraId}
                    disabled={isTrackingActive || isStarting}
                    onChange={(event) => {
                      const camId = event.target.value;
                      setSelectedCameraId(camId);
                      const selected = cameraOptions.find((c) => c.id === camId);
                      if (selected) {
                        setTrackingMode(selected.type === "jetson" ? "device-api" : "browser");
                      }
                    }}
                    className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm font-medium ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {cameraOptions.map((cam) => (
                      <option key={cam.id} value={cam.id}>
                        {cam.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs leading-relaxed text-slate-500">
                    Kamera Jetson Nano terdeteksi secara otomatis dari jaringan. Kamera lokal browser akan muncul di daftar jika diizinkan.
                  </p>
                </div>

                {isTrackingActive ? (
                  <Button variant="destructive" className="w-full" onClick={stopTracking}>
                    <StopCircle className="mr-2 h-5 w-5" /> Stop Tracking
                  </Button>
                ) : (
                  <Button className="w-full" onClick={startTracking} disabled={isStarting}>
                    {isStarting ? (
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    ) : (
                      <PlayCircle className="mr-2 h-5 w-5" />
                    )}
                    {isStarting
                      ? trackingMode === "device-api"
                        ? "Connecting Device..."
                        : "Preparing Models..."
                      : "Start Tracking"}
                  </Button>
                )}

                <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                  <div className="flex items-center gap-2">
                    {trackingMode === "device-api" ? <Network className="h-4 w-4" /> : <Cpu className="h-4 w-4" />}
                    <span>{modelStatus}</span>
                  </div>
                  {trackingMode === "browser" && provider && processingMs > 0 && (
                    <p className="mt-1 text-xs text-slate-500">
                      Runtime: {provider.toUpperCase()} · {inferenceMode ?? "-"} · {processingMs.toFixed(0)} ms/frame
                    </p>
                  )}
                </div>

                {cameraError && (
                  <p className="text-sm leading-relaxed text-red-600">{cameraError}</p>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-2xl border">
              <CardHeader>
                <CardTitle>Detection Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  { key: "emotion", label: "Emotion Detection", available: trackingMode === "device-api" ? true : capabilities.emotion },
                  { key: "head", label: "YOLO Head Detection", available: trackingMode === "device-api" ? true : capabilities.head },
                  { key: "clothing", label: "YOLO Clothing Detection", available: trackingMode === "device-api" ? true : capabilities.clothing },
                  { key: "db_save", label: "Save to Database", available: true },
                ].map(({ key, label, available }) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className={!available ? "text-slate-400" : "font-medium text-slate-700"}>
                      {label}{!available ? " (light mode)" : ""}
                    </span>
                    <input
                      type="checkbox"
                      checked={config[key as keyof TrackingConfig]}
                      disabled={!available}
                      onChange={() => toggleConfig(key as keyof TrackingConfig)}
                      className="h-5 w-5 rounded border-slate-300 text-purple-600 focus:ring-purple-500 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
                    />
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6 xl:col-span-2">
            <Card className="rounded-2xl border shadow-md">
              <CardHeader>
                <CardTitle>Live Feed</CardTitle>
              </CardHeader>
              <CardContent className="flex min-h-[320px] items-center justify-center p-3 sm:min-h-[520px] sm:p-6">
                {!isTrackingActive && !isStarting ? (
                  <div className="text-center text-gray-500">
                    <Settings className="mx-auto mb-3 h-10 w-10" />
                    <p>Press Start Tracking to begin.</p>
                  </div>
                ) : trackingMode === "device-api" ? (
                  <div className="relative flex w-full justify-center overflow-hidden rounded-lg border bg-black">
                    {deviceFeedUrl ? (
                      <img
                        src={deviceFeedUrl}
                        alt="Realtime stream from Jetson or Raspberry Pi"
                        className="max-h-[70vh] w-full object-contain"
                        onLoad={() => appendLog("info", "Device video stream loaded.")}
                        onError={() => {
                          setCameraError("Unable to load the device video stream. Check the API URL and network access.");
                          appendLog("error", "Unable to load /video_feed from the device API.");
                        }}
                      />
                    ) : (
                      <div className="flex min-h-[360px] flex-col items-center justify-center text-white">
                        <Loader2 className="mb-3 h-10 w-10 animate-spin" />
                        <p>Connecting to device stream...</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="relative flex w-full justify-center overflow-hidden rounded-lg border bg-black">
                    <video
                      ref={videoRef}
                      muted
                      playsInline
                      className="max-h-[70vh] w-full object-contain"
                    />
                    <canvas
                      ref={overlayCanvasRef}
                      className="pointer-events-none absolute inset-0 h-full w-full object-contain"
                    />
                    {isStarting && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 text-white">
                        <Loader2 className="mb-3 h-10 w-10 animate-spin" />
                        <p>{modelStatus}</p>
                        <p className="mt-1 text-xs text-white/70">The first model download may take a moment.</p>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {isTrackingActive && (
              <Card className="rounded-2xl border shadow-md">
                <CardHeader>
                  <CardTitle>Person Tracking</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Emotion</TableHead>
                        <TableHead>Head</TableHead>
                        <TableHead>Clothes</TableHead>
                        <TableHead>Duration</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {trackingData.length > 0 ? (
                        trackingData.map((person: any) => (
                          <TableRow key={person.id}>
                            <TableCell>{person.id}</TableCell>
                            <TableCell>
                              {config.emotion && person.emotion !== "-" ? (
                                <>
                                  {person.emotion}
                                  {person.confidence > 0
                                    ? ` (${(person.confidence * 100).toFixed(0)}%)`
                                    : ""}
                                </>
                              ) : (
                                <span className="italic font-normal text-slate-400">Off</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {config.head && person.head !== "-" ? (
                                person.head
                              ) : (
                                <span className="italic font-normal text-slate-400">Off</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {config.clothing && person.clothes !== "-" ? (
                                person.clothes
                              ) : (
                                <span className="italic font-normal text-slate-400">Off</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {person.duration > 0 ? `${person.duration.toFixed(1)}s` : "-"}
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center text-gray-400">
                            No faces detected yet.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}

            {(isTrackingActive || isStarting) && (
              <Card className="rounded-2xl border shadow-md">
                <CardHeader>
                  <CardTitle>Realtime Logs</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-56 overflow-auto rounded-md bg-slate-950 p-3 font-mono text-xs text-slate-100">
                    {realtimeLogs.length > 0 ? (
                      realtimeLogs.map((log, index) => (
                        <div
                          key={`${log.timestamp}-${index}`}
                          className="whitespace-pre-wrap leading-relaxed"
                        >
                          <span className="text-slate-400">[{log.timestamp}]</span>{" "}
                          <span
                            className={
                              log.level === "error"
                                ? "text-red-300"
                                : log.level === "warn"
                                  ? "text-yellow-300"
                                  : log.level === "debug"
                                    ? "text-sky-300"
                                    : "text-emerald-300"
                            }
                          >
                            {log.level.toUpperCase()}
                          </span>{" "}
                          <span>{log.message}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-400">Waiting for initialization...</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
