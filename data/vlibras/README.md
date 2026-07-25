# VLibras reference data

This directory contains metadata and portable animation references generated
from a locally supplied VLibras archive.

- `catalog-v1.json`: deduplicated index of 13,597 Unity animation bundles.
- `reference-clips/`: proof-of-concept portable curve exports.
- `LICENSE-GPL-3.0.txt`: license shipped with the supplied archive.

The original 3.9 GB archive is intentionally excluded from Git and from the
mobile package. The API serves the lightweight catalog with pagination.
Animation files must be delivered on demand from controlled storage rather
than embedded wholesale in the APK.

The source archive is attributed to the VLibras suite produced by
LAViD/UFPB with Brazilian federal-government support. Publishing or
commercially distributing the animations remains disabled until the project
owner confirms the applicable VLibras content terms.
