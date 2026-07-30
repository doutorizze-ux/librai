# VLibras reference data

This directory contains metadata and portable animation references generated
from a locally supplied VLibras archive.

- `catalog-v1.json`: fallback snapshot with 13,597 Unity animation bundles.
- `reference-clips/`: proof-of-concept portable curve exports.
- `LICENSE-GPL-3.0.txt`: license shipped with the supplied archive.

The production API synchronizes the official VLibras trie exposed by
`dicionario2.vlibras.gov.br`, currently containing more than 22 thousand
entries. If that service is temporarily unavailable, `catalog-v1.json` keeps
the dictionary usable in degraded mode. Results are paginated and animation
files are delivered on demand instead of being embedded wholesale in the APK.

The source archive is attributed to the VLibras suite produced by
LAViD/UFPB with Brazilian federal-government support. Publishing or
commercially distributing the animations remains disabled until the project
owner confirms the applicable VLibras content terms.
