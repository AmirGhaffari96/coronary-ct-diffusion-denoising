# Models

## Framing: these are denoisers, not contrast synthesisers

FoundDiff, CoreDiff and NEED are all **low-dose CT denoisers**. They are
trained to map a noisy low-dose CT to its normal-dose counterpart. None of them
synthesises contrast, and none of them has any notion of coronary anatomy.

That determines how they are used here:

- the **input to enhance** is `img.nii.gz`, the non-contrast calcium-score
  scan — this is the genuinely low-dose acquisition in the pair;
- the registered CCTA (`regCCTA_*.nii.gz`) is an **anatomical reference** for
  where the coronaries are. It is *not* a supervised target, and no metric in
  this project treats it as one.

Both volumes were put through both models, so the CCTA numbers show how each
model behaves on a high-dose, contrast-filled scan it was never trained for.

## Side by side

| | FoundDiff | CoreDiff |
|---|---|---|
| upstream | [hao1635/FoundDiff](https://github.com/hao1635/FoundDiff) @ `c85a3a0` | [qgao21/CoreDiff](https://github.com/qgao21/CoreDiff) @ `9bc31dc` |
| checkpoint | `model-400.pt` (EMA @ step 300k) + `DA-CLIP.pth` | `ema_model-150000` (Mayo 2016, 25% dose) |
| architecture | `UnetRes`, dim 64, mults 1/2/4/8, Mamba blocks, DA-CLIP dose encoder | CoreDiff `Network`, 3-channel in / 1-channel out |
| input | single 512² slice | 3-slice context (z−1, z, z+1) |
| HU normalisation | clip [−1000, 2000] → [0,1] | clip [−1024, 3072] → [0,1] |
| diffusion | residual diffusion, `objective='pred_res'` | cold diffusion |
| sampling | residual DDIM, 2 steps | DDIM, T = 10 |
| runtime | ~115 s / 256-slice volume | ~85 s / 256-slice volume |
| batch used | 4 | 8 |

## CoreDiff

Cold diffusion: instead of diffusing toward Gaussian noise, the forward process
interpolates between the normal-dose and low-dose image, so sampling starts
from the actual noisy scan rather than from noise. That is why it converges in
10 steps.

The 3-slice context window is the main practical difference from FoundDiff —
it sees `z−1` and `z+1`, which suppresses the slice-to-slice flicker a purely
2D denoiser can introduce. `ctio.context_stack()` replicates the edge slice at
the top and bottom of the volume.

The released checkpoint is trained on Mayo 2016 at 25% dose.

## FoundDiff

A foundation-model-style denoiser: a DA-CLIP encoder estimates the dose level
of the incoming slice, and that embedding conditions a residual-diffusion UNet
built from Mamba state-space blocks. The intent is one model that generalises
across dose levels rather than one checkpoint per dose.

Two consequences visible in the output here:

- **It denoises the non-contrast scan hardest** (−54% noise SD vs CoreDiff's
  −46%), which is what you would expect from a model whose dose encoder can
  recognise how noisy the input actually is.
- **It clamps HU at −1000.** Air outside the body, which these scans record at
  roughly −3000 HU, is raised to −1000. Irrelevant inside the heart, but it
  shows up as a bright ring in the difference panels of the viewer, and it is
  an artefact of the normalisation, not of the model's denoising.

## NEED

Not runnable here. It is the dual-domain model of the three (a shifted-Poisson
diffusion stage on the raw sinogram, then a doubly-guided Gaussian diffusion
stage on the image), and it is blocked three separate ways — no released
weights, no `torch_radon` build for this CUDA/torch stack, and no projection
data in MIHEART. Full detail, including the fan-beam geometry it would need, is
in [need-status.md](need-status.md).

## Why the upstream training code is bypassed

Neither repo's training entry point is usable as shipped, and neither is needed
— both models are run purely at inference from released weights:

- **FoundDiff `train.py`** references an undefined `folder` variable and
  hard-codes Mayo `.npy` dataset paths.
- **CoreDiff `models/__init__.py`** imports the full training task, including
  `wandb` and a perceptual loss, so importing the package at all drags in
  dependencies inference does not use.

`10_run_corediff.py` therefore imports the two model modules directly by file
path, and `20_run_founddiff.py` constructs `ResidualDiffusion` itself. Both
assert that the checkpoint actually populated the network weights, because a
silent partial load produces output that looks plausible and is wrong.
