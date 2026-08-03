self.exports = {};
importScripts(
  "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/vision_bundle.cjs",
);

const {
  FilesetResolver,
  HandLandmarker,
  PoseLandmarker,
  FaceLandmarker,
} = self.exports;

const POSE_INDICES = [0, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 23, 24];

let handLandmarker = null;
let poseLandmarker = null;
let faceLandmarker = null;
let delegate = "CPU";
let isReady = false;

async function closeLandmarkers() {
  await handLandmarker?.close?.();
  await poseLandmarker?.close?.();
  await faceLandmarker?.close?.();
  handLandmarker = null;
  poseLandmarker = null;
  faceLandmarker = null;
}

async function createLandmarkers(vision, paths, requestedDelegate) {
  handLandmarker = await HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: paths.handModelAssetPath,
      delegate: requestedDelegate,
    },
    runningMode: "VIDEO",
    numHands: 2,
    minHandDetectionConfidence: 0.55,
    minHandPresenceConfidence: 0.55,
    minTrackingConfidence: 0.55,
  });
  poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: paths.poseModelAssetPath,
      delegate: requestedDelegate,
    },
    runningMode: "VIDEO",
    numPoses: 1,
    minPoseDetectionConfidence: 0.5,
    minPosePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
    outputSegmentationMasks: false,
  });
  faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: paths.faceModelAssetPath,
      delegate: requestedDelegate,
    },
    runningMode: "VIDEO",
    numFaces: 1,
    minFaceDetectionConfidence: 0.5,
    minFacePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
    outputFaceBlendshapes: false,
    outputFacialTransformationMatrixes: false,
  });
}

async function initialize(message) {
  if (handLandmarker && poseLandmarker && faceLandmarker) {
    self.postMessage({
      type: isReady ? "ready" : "warmup-request",
      delegate,
    });
    return;
  }

  const vision = await FilesetResolver.forVisionTasks(message.wasmRoot);
  try {
    await createLandmarkers(vision, message, "GPU");
    delegate = "GPU";
  } catch (gpuError) {
    console.warn(
      "MediaPipe holístico GPU indisponível; usando CPU dedicada.",
      gpuError,
    );
    await closeLandmarkers();
    await createLandmarkers(vision, message, "CPU");
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

function serializeHands(result) {
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

function serializePose(result) {
  const pose = result.landmarks?.[0];
  if (!pose) return [];
  return POSE_INDICES.map((index) => {
    const point = pose[index] || { x: 0, y: 0, z: 0 };
    return { x: point.x, y: point.y, z: point.z };
  });
}

function runAll(bitmap, timestampMs) {
  const hands = handLandmarker.detectForVideo(bitmap, timestampMs);
  const pose = poseLandmarker.detectForVideo(bitmap, timestampMs);
  const face = faceLandmarker.detectForVideo(bitmap, timestampMs);
  const expression = dynamicExpression(face.faceLandmarks?.[0]);
  return {
    ...serializeHands(hands),
    poseLandmarks: serializePose(pose),
    poseDetected: Boolean(pose.landmarks?.length),
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
    if (!handLandmarker || !poseLandmarker || !faceLandmarker) {
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
