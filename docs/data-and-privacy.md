# Data and privacy

This project operates on identifiable patient imaging. **No patient-derived
material is committed to this repository** — not images, not metrics, not case
identifiers.

## The source cohort

`MIHEART_REG_PAIRED_BATCH3` — paired non-contrast calcium-score CT and
registered CCTA, with coronary, aorta and whole-heart segmentations already
present per case. It lives on local storage and is **not** in this repository.
Only the filesystem path appears, in `scripts/ctio.py`.

## What is excluded

`.gitignore` keeps all of the following out. Everything here regenerates from
the pipeline against a local copy of the data.

### Patient-derived

| path | what it is |
|---|---|
| `work/outputs/` | denoised NIfTI volumes (~7.0 GB) — full patient scans |
| `work/figures/` | rendered axial CT slices |
| `work/*.json` | metrics and case lists keyed by MIHEART accession ID |
| `viewer/slices/` | per-slice PNG/JPEG renders (~420 MB) — full patient scans |
| `viewer/manifest.json`, `viewer/metrics.json` | case IDs, slice ranges, voxel spacing |
| `logs/` | run logs naming each case as it is processed |

### Large third-party artifacts

| path | what it is |
|---|---|
| `weights/` | checkpoints (~2.4 GB), released by the original authors |
| `envs/` | virtualenv (~279 MB), rebuilt from `requirements.txt` |
| `repos/` | upstream source, cloned at pinned commits by `scripts/clone_upstream.sh` |

## What this means in practice

A fresh clone contains code and documentation only. To get a working setup you
need local access to the MIHEART cohort and must run the pipeline yourself —
see [setup.md](setup.md). That is deliberate.

Accession identifiers are the part people most often overlook. A case ID with
no image attached is still protected information, which is why
`work/*.json`, `viewer/manifest.json` and `logs/` are excluded alongside the
images themselves.

## Aggregate numbers are fine

The tables in [results.md](results.md) and the README are cohort means over 10
cases with no identifiers attached. Those are safe to quote in a paper, a talk
or an issue, and they are the reason this repository is still useful without
the underlying data.

## The viewer

`scripts/serve_viewer.sh` binds `127.0.0.1` and has **no authentication of any
kind**. Reach it over an SSH tunnel; do not change the bind address to
`0.0.0.0`:

```bash
ssh -L 8712:localhost:8712 <user>@<host>
```

## Before you copy anything

Denoised output is still patient data. `work/outputs/*.nii.gz` carries the
original affine and NIfTI header, and a denoised scan is as identifiable as the
scan it came from. Treat those files exactly as you would the source cohort,
and keep them off any host not covered by the governing data agreement.

## If patient data ever does reach a remote

Removing it from the current commit is not enough — it stays reachable in the
history, and on a hosting service it can remain fetchable by commit SHA after a
force-push, independently of what the default branch points at. Rewriting
history limits further exposure but does not by itself undo it. Treat such an
event as a potential disclosure and escalate it to whoever administers the data
agreement rather than resolving it purely technically.
