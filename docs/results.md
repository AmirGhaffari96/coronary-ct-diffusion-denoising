# Results

10 MIHEART cases, both modalities, both models. All values are means over the
10 cases, computed by `scripts/30_evaluate.py` from `work/metrics.json`.
Definitions and ROI construction are in [metrics.md](metrics.md).

![Results](img/results.png)

*Cohort means only — this chart carries no case identifiers and no anatomy.*

## Non-contrast (NCCT) — the scan these models are actually for

| variant | noise SD (HU) | SNR | CNR | edge grad | FP ≥130 HU | HU bias |
|---|---|---|---|---|---|---|
| original | 15.55 | 2.92 | 5.00 | 673.0 | 108.2 | — |
| CoreDiff | 8.39 (**−46%**) | 5.54 (+90%) | 9.47 (+90%) | 612.3 (−9%) | 26.6 (**−75%**) | −0.16 |
| FoundDiff | **7.16 (−54%)** | **6.70 (+130%)** | **11.30 (+126%)** | 593.8 (−12%) | 37.0 (−66%) | +0.60 |

## CCTA — out of distribution for both models

| variant | noise SD (HU) | SNR | CNR | edge grad | HU bias |
|---|---|---|---|---|---|
| original | 44.20 | 10.80 | 5.42 | 1642.6 | — |
| CoreDiff | **28.53 (−35%)** | **24.45 (+127%)** | **12.21 (+125%)** | 1556.1 (−5%) | +1.40 |
| FoundDiff | 31.39 (−29%) | 19.58 (+81%) | 9.70 (+79%) | 1553.6 (−5%) | +3.31 |

`fp130` is not tabulated for CCTA: in a contrast-filled aorta essentially every
lumen voxel exceeds 130 HU (~468k of them), so the metric carries no
information there. It is a calcium-scoring metric and calcium scoring is done
on the non-contrast scan.

## What these numbers say

**The noise/edge trade-off is favourable, which is the whole question.**
Vessel-wall gradient falls 5–12% against a 29–54% drop in noise SD. Noise
reduction alone is trivial — blur hard enough and `noise_sd` goes to zero — so
the gap between those two percentages is the result. Both models are removing
noise rather than anatomy.

**FoundDiff wins on the non-contrast scan; CoreDiff wins on CCTA.** FoundDiff's
dose-aware CLIP encoder is built to recognise how noisy its input is, and the
NCCT is the genuinely low-dose acquisition in the pair, so this is the expected
ordering. On CCTA — high dose, contrast-filled, nothing either model was
trained on — the ordering reverses, and CoreDiff's 3-slice context is the
plausible reason: with more z-context it has more to work with when the
in-plane statistics are unfamiliar.

**HU are preserved.** Mean shift inside the aortic ROI is −0.16 / +0.60 HU on
NCCT and +1.40 / +3.31 HU on CCTA. This is the precondition for everything
else: a denoiser that rescales HU invalidates Agatston scoring outright. NCCT,
the scan that gets scored, holds well under 1 HU.

**Calcium false positives drop by two thirds to three quarters.** Noise spikes
crossing 130 HU inside the aortic lumen fall from 108 per case to 27 (CoreDiff)
or 37 (FoundDiff), while genuine calcium inside the coronary mask (`cac130`)
is essentially preserved — 1502 voxels originally, 1432 and 1474 after. The
models are suppressing spurious calcium candidates without erasing real
calcium. For calcium scoring on a noisy low-dose acquisition that is the single
most useful thing in this table.

Note that CoreDiff achieves the lower false-positive count (26.6 vs 37.0) even
though FoundDiff denoises harder overall — the two do not track each other, and
on this metric CoreDiff is ahead.

## Caveats

- **10 cases, one cohort, one protocol.** Directionally solid; not a clinical
  claim.
- **No reader study.** Nothing here shows a radiologist reads the denoised scan
  better — only that the measured trade-off is favourable.
- **No ground truth.** There is no noise-free acquisition of the same anatomy,
  which is why every metric is no-reference. None of them is PSNR or SSIM
  against a target, because no target exists.
- **`fp130` is measured in the aorta**, not in the coronaries, so it is a proxy
  for calcium false positives rather than a recomputed Agatston score.
- **CCTA results describe behaviour, not fitness.** Both models were applied far
  outside their training distribution there.
- **FoundDiff clips HU at −1000**, raising air outside the body from ~−3000.
  Irrelevant inside the heart, visible as a bright ring in the viewer's
  difference panels.

## Looking at it

Numbers in a table do not show whether a denoiser ate a vessel. Two ways to
check:

- `work/figures/<name>_compare.png` — original / CoreDiff / FoundDiff for
  **both** modalities at a representative cardiac slice, full field and zoomed
  on the coronary with the vessel mask outlined. Generated locally by
  `40_figures.py`; not committed, since these are rendered patient slices.
- The [viewer](viewer.md), in particular the **difference panels** (what each
  model removed — should look like structureless noise, with no vessel
  outlines) and the **before/after swipe**, which puts the divider wherever you
  want to inspect.
