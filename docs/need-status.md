# NEED (Noise-Inspired dual-domain Diffusion) — status

Repo: https://github.com/qgao21/NEED (`repos/NEED`, commit 5d02327)
Paper: "Noise-Inspired Diffusion Model for Generalizable Low-Dose CT
Reconstruction", Med. Image Anal. 2025 — arXiv:2506.22012

NEED is the dual-domain model of the three:

| stage  | domain              | what it does                                          |
|--------|---------------------|-------------------------------------------------------|
| SPDiff | pre-log projection  | shifted-Poisson diffusion, denoises the raw sinogram   |
| DGDiff | image               | doubly-guided Gaussian diffusion, refines the FBP image |

## Verified status on this workstation

| component | constructs? | runnable with pretrained weights? |
|-----------|-------------|-----------------------------------|
| DGDiff (image domain)      | yes — 35.7 M-param UNet builds and samples | **no — no released weights** |
| SPDiff (projection domain) | no — `import torch_radon` fails | **no — no released weights** |

## Three independent blockers

1. **No pretrained weights are released.** Unlike CoreDiff (`ema_model-150000`
   on Google Drive) and FoundDiff (`DA-CLIP.pth` + `model-400.pt` on Google
   Drive), the NEED README has no weights section and the repo contains no
   checkpoint links. Both stages would have to be trained from scratch
   (`train_SPDiff.sh`, then `train_DGDiff_stage1.sh` / `_stage2.sh`).

2. **`torch_radon` is unavailable for this stack.** `SPDiff/models/SPDiff/SPDiff.py`
   imports `RadonFanbeam` from `torch_radon`. That package is not on PyPI
   (`pip download torch-radon` -> "no matching distribution"); it exists only as
   an unmaintained CUDA source extension (matteo-ronchetti/torch-radon) targeting
   torch 1.x / CUDA 10-11. This box runs torch 2.8.0+cu128 on CUDA 13.2, so it
   would need porting, or replacing with a fan-beam projector written against a
   maintained toolkit.

3. **MIHEART has no projection data.** SPDiff consumes pre-log sinograms
   (672 detectors x 672 views fan-beam, `--data_type sino`). The
   MIHEART_REG_PAIRED_BATCH3 cases are reconstructed NIfTI volumes only, so the
   sinograms would have to be forward-simulated — which again needs a projector
   (blocker 2) and makes the "raw data" synthetic anyway.

Blockers 2 and 3 are solvable with engineering. Blocker 1 is not: without
weights there is nothing to run, and training NEED on this data would first
require paired low-dose/normal-dose acquisitions that this cohort does not have.

## What the geometry would be (from `SPDiff.py:80-96`), if this is pursued

```
det_count   = 672        det_spacing = 1.85 / 0.68
n_views     = 672        angles      = linspace(-pi/2, 3pi/2, 672)
src_dist    = 1361.2 - 615.18 = 746.02
det_dist    = 615.18     clip_to_circle = False
u_water     = 0.0192     kappa = 1.5
I0          = 2.5e5      lambda schedule 3e5 -> 2.5e4 over T steps
```
