self.exports = {};
importScripts(
  "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/vision_bundle.cjs",
);

const {
  FilesetResolver,
  HolisticLandmarker,
} = self.exports;

const POSE_INDICES = [0, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 23, 24];

let holisticLandmarker = null;
let delegate = "CPU";
let isReady = false;

async function closeLandmarker() {
  await holisticLandmarker?.close?.();
  holisticLandmarker = null;
}

async function createLandmarker(vision, paths, requestedDelegate) {
  holisticLandmarker = await HolisticLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: paths.holisticModelAssetPath,
      delegate: requestedDelegate,
    },
    runningMode: "VIDEO",
    minHandLandmarksConfidence: 0.5,
    minPoseDetectionConfidence: 0.5,
    minPosePresenceConfidence: 0.5,
    minPoseSuppressionThreshold: 0.3,
    minFaceDetectionConfidence: 0.5,
    minFacePresenceConfidence: 0.5,
    minFaceSuppressionThreshold: 0.3,
    outputFaceBlendshapes: false,
    outputPoseSegmentationMasks: false,
  });
}

async function initialize(message) {
  if (holisticLandmarker) {
    self.postMessage({
      type: isReady ? "ready" : "warmup-request",
      delegate,
    });
    return;
  }

  const vision = await FilesetResolver.forVisionTasks(message.wasmRoot);
  try {
    await createLandmarker(vision, message, "GPU");
    delegate = "GPU";
  } catch (gpuError) {
    console.warn(
      "MediaPipe holístico GPU indisponível; usando CPU dedicada.",
      gpuError,
    );
    await closeLandmarker();
    await createLandmarker(vision, message, "CPU");
    delegate = "CPU";
  }
  self.postMessage({ type: "warmup-request", delegate });
}

function pointDistance(a, b) {
  if (!a || !b) return 0;
  return Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0));
}

function safeRatio(numerator, denominator) {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator < 1e-6) {
    return 0;
  }
  return numerator / denominator;
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, Number(value || 0)));
}

function dynamicExpression(face) {
  if (!face || face.length < 387) {
    return {
      detected: false,
      values: { mouth_open: 0, mouth_width: 0, left_brow: 0, right_brow: 0 },
    };
  }
  const faceScale = Math.max(pointDistance(face[33], face[263]), 1e-6);
  return {
    detected: true,
    values: {
      mouth_open: clamp(
        safeRatio(pointDistance(face[13], face[14]), faceScale), 0, 2,
      ),
      mouth_width: clamp(
        safeRatio(pointDistance(face[61], face[291]), faceScale), 0, 2,
      ),
      left_brow: clamp(
        safeRatio(face[159].y - face[105].y, faceScale), -1, 1,
      ),
      right_brow: clamp(
        safeRatio(face[386].y - face[334].y, faceScale), -1, 1,
      ),
    },
  };
}

function serializeHand(hand) {
  return hand.map(({ x, y, z }) => ({ x, y, z }));
}

function serializeHands(result) {
  const landmarks = [];
  const handedness = [];
  for (const hand of result.leftHandLandmarks || []) {
    landmarks.push(serializeHand(hand));
    handedness.push([{ label: "Left", score: 1 }]);
  }
  for (const hand of result.rightHandLandmarks || []) {
    landmarks.push(serializeHand(hand));
    handedness.push([{ label: "Right", score: 1 }]);
  }
  return { landmarks, handedness };
}

function serializePose(result) {
  const pose = result.poseLandmarks?.[0];
  if (!pose) return [];
  return POSE_INDICES.map((index) => {
    const point = pose[index] || { x: 0, y: 0, z: 0 };
    return { x: point.x, y: point.y, z: point.z };
  });
}

function runAll(bitmap, timestampMs) {
  const result = holisticLandmarker.detectForVideo(bitmap, timestampMs);
  const expression = dynamicExpression(result.faceLandmarks?.[0]);
  return {
    ...serializeHands(result),
    poseLandmarks: serializePose(result),
    poseDetected: Boolean(result.poseLandmarks?.length),
    faceDetected: expression.detected,
    expression: expression.values,
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
      runAll(message.bitmap, 1);
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
    if (!holisticLandmarker) {
      throw new Error("Rastreamento holístico ainda não foi inicializado.");
    }
    self.postMessage({
      type: "result",
      sessionId,
      timestampMs,
      inferenceLatencyMs: Math.round(performance.now() - startedAt),
      ...runAll(bitmap, timestampMs),
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
