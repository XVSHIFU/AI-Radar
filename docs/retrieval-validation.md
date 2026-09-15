# Retrieval validation

## Earlier CPU feasibility run (mean pooling; superseded profile)

Measured on the Ubuntu development VM (8 vCPU, 7.2 GiB RAM) on 2026-09-15.

- Runtime: ONNX Runtime CPU, four intra-op threads, mean pooling over the attention mask,
  L2 normalization, maximum input length 512.
- Model: `libryo-ai/BAAI-bge-m3-int8`, revision
  `7698c0c30eafe2736771e96d733545270cdec56f`, MIT license.
- `model.onnx` SHA-256:
  `796e1f3985226cb8e5b3b52f9c70154c82ab3d65cfed13fdf6faea03aae67cd3`.
- Artifact size: 560 MiB. Optional runtime environment: 185 MiB.
- A real two-text Chinese/English inference returned finite normalized vectors with shape
  `[2, 1024]`. The first run, including download, took 74.53 seconds and peaked at
  1,357,544 KiB RSS without swap.

This proves that the pinned profile can execute on this VM. It does not establish semantic
recall quality. Recall remains unverified until a labeled retrieval set is run. Flash is used
for answer generation and does not provide embeddings.

The model cache is provisioned outside Git. The API must not load one copy per web worker;
use a single lazy worker or an external embedding process on this VM.

## Integration correction

The earlier run proves CPU/memory feasibility only. Review found its mean pooling did
not match [BAAI's published BGE-M3 pooling configuration](https://huggingface.co/BAAI/bge-m3/blob/main/1_Pooling/config.json),
which selects CLS. The adapter now uses CLS + L2 normalization and profile template
`plain-cls512-v2`; vectors from the old template cannot be mixed with the new profile.
CPU inference/lazy model loading are serialized to avoid concurrent model copies.
The corrected profile still needs real-model integration and labeled Recall evaluation.
