# Pipeline

Six scripts, numbered in execution order. Each writes into `work/` or
`viewer/` and is safe to re-run — the inference steps skip any output file that
already exists, so a crashed run resumes rather than restarting.

All of them are run with the project interpreter:

```bash
envs/diffct/bin/python scripts/<script>.py
```

---

## `ctio.py` — shared IO (not a step)

The one place where each model's HU convention is written down, so the same
volume can be fed to both without silently mismatching the range the network
was trained on:

| model | HU clip | mapping to [0,1] |
|---|---|---|
| CoreDiff | `[-1024, 3072]` | `(HU + 1024) / 4096` |
| FoundDiff | `[-1000, 2000]` | `(HU + 1000) / 3000` |

Also provides `case_paths()` (the per-case file layout), `load_hu()` /
`save_like()` (NIfTI IO that preserves the source affine and forces
`scl_slope=1, scl_inter=0` so output HU are literal), and `context_stack()`
(the 3-slice `[z-1, z, z+1]` neighbourhood CoreDiff expects, with edge
replication at the volume ends).

---

## `00_select_cases.py` — screen and select 10 cases

Walks every case in `MIHEART_REG_PAIRED_BATCH3` and keeps those where:

- `img.nii.gz`, `regCCTA_*.nii.gz` and `coronary_branches.nii.gz` all exist
- all three share a 512x512xZ shape, and NCCT/CCTA affines match to 1e-3
  (i.e. the pair is already registered)
- all 4 coronary branch labels are present

Survivors are ranked by coronary mask volume descending — a bigger vessel mask
gives a more stable ROI statistic downstream — then 10 are taken evenly spaced
across the top half of the ranking, so the sample is not just the 10 largest
hearts.

**Writes** `work/all_cases.json` (every eligible case + geometry),
`work/selected_cases.json` (the 10 that the rest of the pipeline consumes).

---

## `10_run_corediff.py` — CoreDiff inference

Loads `ema_model-150000` into CoreDiff's `Diffusion` wrapper (`image_size=512`,
`timesteps=10`, `context=True`) and denoises slice by slice with cold-diffusion
DDIM sampling.

It imports `models/corediff/corediff_wrapper.py` and
`models/corediff/diffusion_modules.py` **directly by file path** rather than as
a package, because `models/__init__.py` pulls in the whole training task —
`wandb`, a perceptual loss — none of which inference needs.

Key flags: `--modalities ncct ccta`, `--batch 8`, `--cardiac_only` (restrict to
slices spanning the coronary mask plus `--margin`, default 12), `--limit N`.

**Writes** `work/outputs/<case>/{ncct,ccta}_corediff.nii.gz`. ~85 s per
256-slice volume.

---

## `20_run_founddiff.py` — FoundDiff inference

Builds `UnetRes` (dim 64, mults 1/2/4/8, Mamba blocks, `objective='pred_res'`)
inside `ResidualDiffusion` and loads the EMA weights out of `model-400.pt`.
Sampling is residual DDIM with `--sampling_timesteps 2`.

Three things here are not obvious:

1. The script `os.chdir()`s into the FoundDiff repo before importing, because
   `src/DADiff.py` does `torch.load('Dose-CLIP.pth')` with a *relative* path.
2. The EMA state dict is extracted by stripping the `ema_model.` prefix, and
   the load asserts that no key starting with `model.` was left unfilled — a
   silent partial load here produces plausible-looking but wrong output.
3. `diffusion.init()` is called after `.to(device)` to rebuild the
   DDIM-converted schedule, mirroring what the upstream `trainer.test()` does.
   Skipping it gives the training schedule and much worse results.

FoundDiff's own `train.py` cannot be used as shipped: it references an
undefined `folder` variable and hard-codes Mayo `.npy` paths.

**Writes** `work/outputs/<case>/{ncct,ccta}_founddiff.nii.gz`. ~115 s per
256-slice volume.

---

## `30_evaluate.py` — no-reference image-quality metrics

There is no noise-free ground truth for these scans, so everything is
ROI-based and computed in HU. See [metrics.md](metrics.md) for the definitions
and the reasoning behind the ROI construction.

**Writes** `work/metrics.json` — one row per (case, modality, variant).

---

## `40_figures.py` — comparison figures

Picks the axial slice carrying the most coronary voxels and renders four rows:
non-contrast full and zoom, then CCTA full and zoom, each showing original /
CoreDiff / FoundDiff side by side. The zoom crops to the coronary centroid and
outlines the vessel mask in red.

Each modality uses its own display window (NCCT −100..300 HU, CCTA
−100..700 HU) — contrast-filled lumen sits far above non-contrast tissue, so
one shared window would make one or the other unreadable.

`--anonymise` titles and names the figures by index (`case-01`) instead of the
accession ID, which is otherwise rendered into the image itself.

**Writes** `work/figures/<name>_compare.png`. Gitignored — these are patient
images; see [data-and-privacy.md](data-and-privacy.md).

---

## `50_export_viewer_slices.py` — viewer export

Bakes every slice of every panel to PNG at fixed window/level, so the browser
viewer does not have to decode NIfTI.

Also exports vCCTA v6 panels when a prediction exists for the case, looking in
`vCCTA_V6/results/eval_final_test/nifti` (the 100 hold-out cases) and then
`work/vccta/` (generated for the rest), and records each case's vCCTA_V6 split
in the manifest so the viewer can badge it.

**Writes** `viewer/slices/<case>/<panel>/*.png` (~420 MB) and
`viewer/manifest.json`. See [viewer.md](viewer.md).

---

## `serve_viewer.sh` — local viewer server

Threaded `http.server` on `127.0.0.1:8712`. Loopback-only by design; see
[viewer.md](viewer.md) for remote access.

---

## Full run

```bash
envs/diffct/bin/python scripts/00_select_cases.py
envs/diffct/bin/python scripts/10_run_corediff.py  --modalities ncct ccta --batch 8
envs/diffct/bin/python scripts/20_run_founddiff.py --modalities ncct ccta --batch 4
envs/diffct/bin/python scripts/30_evaluate.py
envs/diffct/bin/python scripts/40_figures.py
envs/diffct/bin/python scripts/50_export_viewer_slices.py
./scripts/serve_viewer.sh
```

End to end on 10 cases x 2 modalities x 2 models: roughly 70 minutes of GPU
time, plus a few minutes for evaluation and export.

## A note on paths

Every script defaults its `--cases`, `--out` and `--json` arguments to absolute
paths under `/mnt/raid2/amirg/Diff Models`, and `ctio.ROOT` hard-codes the data
location. On any other machine these must be edited or overridden on the
command line. This is the main thing standing between the repository and
portability.
