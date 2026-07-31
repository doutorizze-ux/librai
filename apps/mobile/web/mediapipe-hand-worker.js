self.exports = {};
importScripts(
  "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/vision_bundle.cjs",
);

const { FilesetResolver, HandLandmarker } = self.exports;

let handLandmarker = null;
let delegate = "CPU";
let isReady = false;

async function createLandmarker(wasmRoot, modelAssetPath, requestedDelegate) {
  const vision = await FilesetResolver.forVisionTasks(wasmRoot);
  return HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath,
      delegate: requestedDelegate,
    },
    runningMode: "VIDEO",
    numHands: 2,
    minHandDetectionConfidence: 0.55,
    minHandPresenceConfidence: 0.55,
    minTrackingConfidence: 0.55,
  });
}

async function initialize({ wasmRoot, modelAssetPath }) {
  if (handLandmarker) {
    self.postMessage({
      type: isReady ? "ready" : "warmup-request",
      delegate,
    });
    return;
  }

  try {
    handLandmarker = await createLandmarker(
      wasmRoot,
      modelAssetPath,
      "GPU",
    );
    delegate = "GPU";
  } catch (gpuError) {
    console.warn(
      "MediaPipe GPU indisponível no worker; usando CPU dedicada.",
      gpuError,
    );
    handLandmarker = await createLandmarker(
      wasmRoot,
      modelAssetPath,
      "CPU",
    );
    delegate = "CPU";
  }

  self.postMessage({ type: "warmup-request", delegate });
}

function serializeResult(result) {
  return {
    landmarks: (result.landmarks || []).map((hand) =>
      hand.map(({ x, y, z }) => ({ x, y, z })),
    ),
    handedness: (result.handedness || []).map((categories) =>
      categories.map((category) => ({
        label: category.categoryName || category.displayName || "Unknown",
        score: Number(category.score || 0),
      })),
    ),
  };
}

self.onmessage = async (event) => {
  const message = event.data || {};

  if (message.type === "init") {
    try {
      await initialize(message);
    } catch (error) {
      self.postMessage({
        type: "init-error",
        message: error?.message || String(error),
      });
    }
    return;
  }

  if (message.type === "warmup" && message.bitmap) {
    try {
      handLandmarker.detectForVideo(message.bitmap, 1);
      isReady = true;
      self.postMessage({ type: "ready", delegate });
    } catch (error) {
      self.postMessage({
        type: "init-error",
        message: error?.message || String(error),
      });
    } finally {
      message.bitmap.close();
    }
    return;
  }

  if (message.type !== "frame" || !message.bitmap) return;

  const { bitmap, timestampMs, sessionId } = message;
  const startedAt = performance.now();

  try {
    if (!handLandmarker) {
      throw new Error("Hand Landmarker ainda não foi inicializado.");
    }
    const result = handLandmarker.detectForVideo(bitmap, timestampMs);
    self.postMessage({
      type: "result",
      sessionId,
      timestampMs,
      inferenceLatencyMs: Math.round(performance.now() - startedAt),
      ...serializeResult(result),
    });
  } catch (error) {
    self.postMessage({
      type: "frame-error",
      sessionId,
      message: error?.message || String(error),
    });
  } finally {
    bitmap.close();
  }
};
