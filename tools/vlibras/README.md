# VLibras reference importer

These tools inspect an externally supplied VLibras archive without executing
its legacy binaries.

- `build_catalog.py` merges the Android, iOS and Linux bundle indexes.
- `extract_animation.py` converts one UnityFS `AnimationClip` to portable JSON.
- `export_archive.py` performs a resumable, parallel, compressed full export.
- `extract_landmark_motion.py` combines the original avatar rest pose and an
  animation clip into lightweight body and 21-point hand sequences.

Install dependencies in an isolated environment:

```powershell
python -m venv tmp/vlibras-tools-venv
tmp/vlibras-tools-venv/Scripts/python -m pip install -r tools/vlibras/requirements.txt
```

The upstream archive is GPL-3.0 and its content can be subject to additional
VLibras terms. Generated files retain source and license attribution. Do not
publish the animation catalog or bundles until distribution rights are
confirmed.
