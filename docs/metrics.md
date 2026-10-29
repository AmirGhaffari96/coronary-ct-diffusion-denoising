# Metrics

There is no noise-free ground truth for these scans — the "low-dose" input is
the only acquisition of that anatomy at that moment. So every metric here is
**no-reference or ROI-based**, computed in HU, and chosen because it matters for
coronary reading rather than because it is easy.

Computed by `scripts/30_evaluate.py`, written to `work/metrics.json` as one row
per (case, modality, variant), where variant is `original`, `corediff` or
`founddiff`.

## The two ROIs

Everything rests on two regions, and how they are built is the part most worth
scrutinising.

### Aortic lumen core — for noise

Source: `ai_cac_aorta_calibration_seg.nii.gz`.

The supplied segmentation spans the whole vessel, so a plain SD over it
measures anatomy — wall, calcium, contrast gradient — rather than noise. So per
axial slice the code keeps only the **largest connected lumen component, eroded
9 in-plane iterations (~4.4 mm)**. This is the digital equivalent of a
radiographer dropping a small circular ROI in the middle of the lumen.

The erosion depth was not arbitrary:

| erosion | NCCT noise SD | CCTA noise SD |
|---|---|---|
| 3 voxels | ~14.5 HU | ~93 HU (lumen-wall edge still leaking) |
| 9 voxels | ~14.5 HU | ~31 HU |

NCCT is flat at any depth — there is no contrast edge to leak. CCTA is not, and
a shallow erosion would have inflated the CCTA noise estimate threefold. Nine
iterations puts both modalities on a clean interior ROI while still leaving
>450k voxels.

### Coronary mask and shells — for contrast and edges

Source: `coronary_branches.nii.gz`.

- **vessel** = mask > 0
- **perivascular** = a 2–4 voxel ring around the vessel (dilate 4, minus
  dilate 2), i.e. the tissue the vessel must stand out against
- **wall** = a 1-voxel shell straddling the vessel boundary (dilate 1, minus
  erode 1), i.e. exactly where a denoiser would blur an edge

All dilations use a `(3,3,1)` structuring element — in-plane only, because
slice thickness (0.625 mm) and in-plane spacing (0.39 mm) are not comparable.

## The metrics

| key | definition | direction |
|---|---|---|
| `noise_sd` | median over axial slices of the 2–98% trimmed in-slice SD inside the aortic core | **lower is better** |
| `aorta_mean` | matching trimmed mean — the signal level for SNR | — |
| `snr` | `aorta_mean / noise_sd` | higher |
| `cnr` | `(mean_vessel − mean_perivascular) / noise_sd` | higher |
| `edge_grad` | mean Sobel gradient magnitude on the wall shell | **should not drop much** |
| `fp130` | voxels ≥ 130 HU inside the aortic core | lower |
| `cac130` | voxels ≥ 130 HU inside the coronary mask | should survive |
| `hu_bias` | mean HU shift vs the original inside the aortic core | **should be ~0** |

### Why `noise_sd` is a median of trimmed per-slice SDs

A single SD over the whole 3D lumen would measure the along-z variation in
aortic enhancement, which on CCTA is substantial, rather than noise. Working
slice by slice removes that. Trimming the 2% tails on each slice removes
calcium specks and partial-volume voxels that would otherwise dominate.

### Why `edge_grad` is the one that matters

Noise reduction is trivial to achieve — blur hard enough and `noise_sd` goes to
zero. `edge_grad` on the vessel wall is the counterweight: it is the failure
mode this whole evaluation exists to catch. A denoiser that drops noise 50% and
edge gradient 50% has done nothing useful.

The result ([results.md](results.md)) is a 30–54% noise drop against a 5–12%
edge-gradient drop, which is the separation you want.

### Why `fp130` and `hu_bias` are here

Both are specific to **calcium scoring**, which is the clinical point of the
non-contrast scan:

- Agatston scoring thresholds at 130 HU. Noise spikes inside the aortic lumen
  that cross 130 HU are false calcium candidates. `fp130` counts them, and it
  falls from 108 to 27 (CoreDiff) / 37 (FoundDiff) per case.
- Any denoiser that rescales HU invalidates the score outright. `hu_bias` is
  the guard, and it holds to within ~0.6 HU on NCCT (3.3 HU on CCTA).

`cac130` is the other side of the same coin: genuine calcium inside the
coronary mask should *survive* denoising, not be smoothed away.

## Reading `work/metrics.json`

```python
import json, pandas as pd
df = pd.DataFrame(json.load(open('work/metrics.json')))
df.groupby(['modality', 'variant'])[
    ['noise_sd', 'snr', 'cnr', 'edge_grad', 'fp130', 'hu_bias']
].mean().round(2)
```

## Limits

- Ten cases from one cohort, one scanner protocol. The percentages are
  directionally solid and not a clinical claim.
- No reader study. Nothing here establishes that a radiologist reads the
  denoised scan better, only that the noise/edge trade-off is favourable.
- `fp130` is measured in the aorta, not in the coronary arteries, so it is a
  proxy for calcium false positives rather than a recomputed Agatston score.
- CCTA is out of distribution for both models — they were trained on low-dose
  non-contrast-style data. Those numbers describe behaviour, not fitness for
  purpose.
