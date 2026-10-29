# Troubleshooting

Things that actually went wrong here, and what they mean.

## `00_select_cases.py` prints `screened 0 eligible cases`

`ctio.ROOT` does not point at the data. It is hard-coded:

```python
ROOT = '/home/amirg/mnt/raid2/chenyu/MIHEART_REG_PAIRED_BATCH3'
```

If the path is right and you still get 0, a case is being rejected by one of
the screening conditions — all volumes must be 512×512×Z, NCCT and CCTA affines
must match to 1e-3, and all 4 coronary labels must be present. The script
rejects silently; add a `print` in the loop to see which condition fires.

## FoundDiff: `FileNotFoundError: Dose-CLIP.pth`

`src/DADiff.py` loads that file by a path relative to the FoundDiff repo root.
`20_run_founddiff.py` therefore `os.chdir()`s into the repo before importing —
if you lifted its model-building code elsewhere without the `chdir`, this is
why. Also confirm the symlink exists:

```bash
ls -l repos/FoundDiff/Dose-CLIP.pth    # -> weights/FoundDiff/DA-CLIP.pth
```

`scripts/clone_upstream.sh` recreates it.

## FoundDiff: output looks plausible but washed out or over-smoothed

Three causes, in order of likelihood:

1. **`diffusion.init()` not called after `.to(device)`.** This rebuilds the
   DDIM-converted sampling schedule. Without it you sample on the training
   schedule and the output is visibly worse while never erroring.
2. **EMA weights not actually loaded.** The state dict is nested under an
   `ema_model.` prefix inside `model-400.pt`. `20_run_founddiff.py` strips it
   and then asserts no key starting with `model.` was left unfilled — keep that
   assert. A partial load produces exactly this symptom.
3. Wrong HU normalisation. FoundDiff is [−1000, 2000], CoreDiff is
   [−1024, 3072]. Feeding one model the other's range degrades output without
   any error.

## CoreDiff: `ModuleNotFoundError: wandb` on import

You imported `models` as a package. `models/__init__.py` pulls in the full
training task. `10_run_corediff.py` loads `corediff_wrapper.py` and
`diffusion_modules.py` directly by file path to avoid this.

## `import mamba_ssm` fails

It compiles CUDA extensions against the torch present at install time. If torch
was upgraded afterwards, reinstall it:

```bash
envs/diffct/bin/pip install --no-build-isolation --force-reinstall mamba-ssm==2.3.2.post1
```

`--no-build-isolation` matters — without it pip builds against a fresh torch it
downloads itself, not yours.

## CUDA out of memory

Lower `--batch` (CoreDiff default 8, FoundDiff 4). FoundDiff is the heavier of
the two. `--cardiac_only` also helps: it restricts inference to slices spanning
the coronary mask plus `--margin` (default 12), typically a third of the
volume.

## `nvidia-smi` says `Driver/library version mismatch`

The kernel module and userspace libraries are out of step, usually after an
unattended driver upgrade without a reboot. Reboot. Until then CUDA is
unavailable and both inference scripts fail at `device='cuda'`.

## A run died partway through

Just re-run it. Both inference scripts skip any output file that already
exists (`[corediff] skip existing ...`), so a crashed run resumes rather than
restarting. The corollary: if you change a model setting, **delete the old
outputs first** or they will be silently kept.

## Viewer is blank / slices 404

`viewer/slices/` is gitignored and not present on a fresh clone. Run
`50_export_viewer_slices.py` to generate it. Check the browser console: 404s on
`slices/<case>/<panel>/0150.jpg` mean that panel was never exported.

## Viewer loads very slowly

It preloads every slice of every active panel on case load — around 800 images.
Make sure you are running `scripts/serve_viewer.sh` and not a plain
`python -m http.server`: the script uses a **threaded** server, and a
single-threaded one serialises those requests. Turning off panels you are not
looking at also helps.

## Viewer: HU readout looks slightly off

Expected. Slices are baked to 8-bit at a fixed window per kind, and the readout
infers HU back from that range — roughly ±4 HU on NCCT. For exact values read
the NIfTI in `work/outputs/` directly. HU outside the baked range are clipped
and cannot be recovered by moving the window/level sliders.

## NEED does not run

It cannot. Three independent blockers, no released weights among them — see
[need-status.md](need-status.md).
