# Setup

Nothing in this repository is runnable on its own: the model source, the
checkpoints, the Python environment and the patient data all live outside it.
This page reconstructs each one.

## 0. Hardware and OS this was run on

| | |
|---|---|
| host | `wonko` (Linux 6.17, Ubuntu OEM kernel) |
| GPU | single CUDA device, CUDA 13.2 driver |
| Python | 3.11.15 |
| torch | 2.8.0+cu128 |

A CUDA GPU is required. Both models sample at 512x512 per slice; CoreDiff
batches 8 slices, FoundDiff 4. Reduce `--batch` if you hit OOM.

## 1. Upstream model source

```bash
./scripts/clone_upstream.sh
```

This clones into `repos/` at the three commits this project was validated
against:

| repo | upstream | commit |
|---|---|---|
| CoreDiff | <https://github.com/qgao21/CoreDiff> | `9bc31dc` |
| FoundDiff | <https://github.com/hao1635/FoundDiff> | `c85a3a0` |
| NEED | <https://github.com/qgao21/NEED> | `5d02327` |

They are **not** vendored here. Each carries its own licence and its own git
history, and nothing in them was modified — the only local change is the
`Dose-CLIP.pth` symlink, which the script recreates. Pinning by commit matters:
FoundDiff in particular has had force-pushed uploads, so `main` is not stable.

## 2. Checkpoints

Not redistributable from here (~2.4 GB, released by the original authors on
Google Drive). Download them from the upstream READMEs and place them as:

```
weights/
  CoreDiff/ema_model-150000        # Mayo 2016, 25% dose
  FoundDiff/model-400.pt           # EMA @ step 300k
  FoundDiff/DA-CLIP.pth            # dose-aware CLIP encoder
```

`scripts/clone_upstream.sh` links `repos/FoundDiff/Dose-CLIP.pth` to
`weights/FoundDiff/DA-CLIP.pth`, because `src/DADiff.py` loads that file by a
path relative to the FoundDiff repo root.

NEED ships no weights at all — that is the first of three blockers described in
[need-status.md](need-status.md).

## 3. Python environment

The original environment is a venv layered on a shared base interpreter with
`--system-site-packages`:

```bash
python3.11 -m venv --system-site-packages envs/diffct
envs/diffct/bin/pip install -r requirements.txt
```

`requirements.txt` records the versions actually used. Two of them are load-bearing:

- **torch 2.8.0+cu128** — install the matching CUDA wheel for your driver, not
  the default PyPI build.
- **mamba-ssm 2.3.2.post1** — FoundDiff's UNet uses Mamba blocks. This builds
  CUDA extensions from source and is the most fragile install in the list; it
  must be built against the same torch version you intend to run.

## 4. Patient data

The pipeline reads `MIHEART_REG_PAIRED_BATCH3`, which is **not** in this
repository and never will be. The path is currently hard-coded in
`scripts/ctio.py`:

```python
ROOT = '/home/amirg/mnt/raid2/chenyu/MIHEART_REG_PAIRED_BATCH3'
```

Change it there to point at your copy. Per case, the pipeline expects:

```
<CASE>/
  img.nii.gz                            # non-contrast calcium-score scan (the input)
  regCCTA_*.nii.gz                      # CCTA, registered to img
  coronary_branches.nii.gz              # 4-label coronary segmentation
  ai_cac_aorta_calibration_seg.nii.gz   # aortic calibration segmentation
  whole_heart.nii.gz                    # optional, sanity checks only
```

All volumes must share a 512x512xZ grid and affine. `00_select_cases.py`
enforces this and silently skips cases that fail.

See [data-and-privacy.md](data-and-privacy.md) before copying any of it
anywhere.

## 5. Verify

```bash
envs/diffct/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
envs/diffct/bin/python -c "import mamba_ssm; print('mamba ok')"
envs/diffct/bin/python scripts/00_select_cases.py
```

The last one should print `screened N eligible cases` and a 10-row table. If it
prints `screened 0`, `ROOT` is wrong.
