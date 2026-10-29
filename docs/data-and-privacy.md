# Data and privacy

This project operates on identifiable patient imaging.

**This repository is public, and no patient-derived material is committed to
it** — not images, not metrics, not case identifiers, not viewer screenshots.
That is a standing policy, not a description of the current state: the
exclusion is permanent and `.gitignore` enforces it.

The reasoning is simple. Everything excluded regenerates from the pipeline in
minutes, so keeping it out costs nothing; putting it in cannot be undone,
because anything that reaches a public remote may be cloned, cached or indexed
before it is removed.

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

## What may be added to `docs/img/`

Only material that contains no patient data. At present:

| file | why it is safe |
|---|---|
| `pipeline.svg` | a diagram — no imaging, no identifiers |
| `results.png` | cohort means over 10 cases — no identifiers, no anatomy |

**Viewer screenshots do not qualify.** They show patient anatomy, and the case
selector and header show the accession ID. Neither does any output of
`40_figures.py`: those render patient slices, and `fig.suptitle` burns the
accession ID into the pixels, so renaming the file does not de-identify it.
Both are blocked in `.gitignore`.

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

This has happened once in this repository's history, so the lesson is recorded
here rather than left to memory.

Removing the data from the current commit is **not** enough. It stays reachable
in the history, and on GitHub it remains fetchable by commit SHA after a
force-push, independently of what the default branch points at — verified, not
assumed. Rewriting history limits further exposure but does not undo it.

The only reliable removals are deleting the repository outright, or asking
GitHub Support to purge the unreachable objects. Either way, treat the event as
a potential disclosure and escalate it to whoever administers the data
agreement; it is not a question a technical fix closes.
