# LIBRAS-EQT-UECE — signer-independent experiments

Date: 2026-07-27

These experiments are research-only. None of the evaluated models was added to
the production application.

## Dataset integrity

- Source: <https://doi.org/10.5281/zenodo.20497742>
- RGB archive: 8,971,968,030 bytes
- RGB MD5: `aff0885616db0281e3913f4b7a26db56` (verified)
- Landmarks archive: 773,596,409 bytes
- Landmarks MD5: `415a18d9be6d65468bcf92db5e940df8` (verified)
- 178 classes
- 5,347 videos
- 5 informants
- All 5,347 RGB videos have an exact hand-landmark pair.

## Evaluation protocol

- Train: informants 1–4 (4,283 samples)
- Test: informant 5 only (1,064 samples)
- No sample from informant 5 is used during training.
- All 178 classes are included.
- Selection criterion for production: at least 90% top-1 plus validation over
  all five signer holdouts and an on-device latency test.

## Results

| Model | Top-1 | Top-3 | Decision |
|---|---:|---:|---|
| Raw hand-landmark temporal Conv baseline | 73.59% | 87.78% | Reject |
| Full-frame MobileNetV3 + temporal Conv | 6.95% | 13.91% | Reject |
| Full-frame RGB + hand landmarks | 22.18% | 44.45% | Reject |
| Landmark-guided hand crops | 15.41% | 34.12% | Reject |
| Hand crops + hand landmarks | 40.04% | 62.22% | Reject |
| Motion-TCN (coordinates + velocity + acceleration) | **78.57%** | **92.48%** | Reject |

The full-frame and crop experiments use an ImageNet-pretrained MobileNetV3
Small encoder. Their poor signer-independent results show that this generic 2D
encoder is not an adequate video sign recognizer for this dataset.

The Motion-TCN improves top-1 by approximately five percentage points over the
raw-landmark baseline, confirming that explicit temporal derivatives are
useful. It remains below the production threshold.

## Next controlled experiment

Use a sign/video-pretrained temporal backbone (for example I3D or VideoMAE) on
a compatible NVIDIA/ROCm environment, then:

1. evaluate all five signer holdouts;
2. report mean, minimum and standard deviation of top-1/top-3;
3. measure continuous-stream false positives and segmentation;
4. export only a model that passes accuracy and on-device latency gates.

The local RX 580 works with PyTorch DirectML for 2D convolution, but its
DirectML backend failed on the required 3D convolution path. Production
integration must not proceed from the current results.
