"""Coronary-focused image-quality evaluation of the denoised volumes.

There is no noise-free ground truth for these scans, so we use no-reference /
ROI-based metrics that matter for coronary reading, all computed in HU:

  noise_sd     SD inside an eroded aortic-root lumen ROI (homogeneous blood
               pool) -> pure noise. Lower is better.
  snr          mean / SD in that same ROI.
  cnr          (mean_vessel - mean_perivascular) / noise_sd, using the
               coronary_branches mask and a shell around it.
  edge_grad    mean Sobel gradient magnitude on the vessel wall shell. A large
               drop relative to the original means the denoiser is blurring
               vessel edges, which is the failure mode we care about.
  fp130        voxels >= 130 HU inside the aortic lumen ROI. On a non-contrast
               calcium-score scan these are pure noise spikes, i.e. calcium
               false-positive candidates. Lower is better.
  cac130       voxels >= 130 HU inside the coronary mask (calcium candidates
               that should survive denoising).
  hu_bias      mean HU shift vs the original inside the aortic ROI; should be
               ~0, a denoiser must not rescale HU.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctio

MODELS = ['corediff', 'founddiff']


def aorta_roi(aorta_path, shape, erode=9):
    """Homogeneous aortic-lumen ROI used for noise statistics.

    The supplied aorta segmentation spans the whole vessel, so a plain SD over
    it is dominated by anatomy (wall, calcium, contrast gradient) rather than
    noise. We therefore keep, per axial slice, only the deeply eroded interior
    of the largest lumen component -- the CT-QC equivalent of dropping a small
    circular ROI in the lumen.

    The erosion depth matters: on CCTA a 3-voxel margin still leaks lumen-wall
    edge voxels and inflates the SD from ~31 HU to ~93 HU, while the NCCT SD is
    flat at ~14.5 HU for any depth (no contrast edge to leak). 9 in-plane
    iterations (~4.4 mm) puts both modalities on a clean interior ROI and still
    leaves >450k voxels.
    """
    if not os.path.exists(aorta_path):
        return None
    a, _, _ = ctio.load_hu(aorta_path)
    m = a > 0
    if m.sum() == 0:
        return None
    keep = np.zeros_like(m)
    for z in range(m.shape[2]):
        sl = m[:, :, z]
        if sl.sum() < 200:
            continue
        lab, n = ndi.label(sl)
        if n == 0:
            continue
        sizes = ndi.sum(sl, lab, range(1, n + 1))
        big = lab == (int(np.argmax(sizes)) + 1)
        core = ndi.binary_erosion(big, structure=np.ones((3, 3), bool), iterations=erode)
        if core.sum() >= 50:
            keep[:, :, z] = core
    return keep if keep.sum() > 500 else None


def robust_noise(hu, roi):
    """Median over axial slices of the trimmed in-slice SD inside the ROI.

    Working slice-by-slice keeps genuine anatomy out of the noise estimate: on
    CCTA the aortic enhancement varies substantially along z, so a single SD
    over the whole 3D lumen measures that gradient rather than noise. Trimming
    the 2% tails per slice removes calcium and partial-volume voxels.
    """
    sds, means = [], []
    for z in range(hu.shape[2]):
        sl = roi[:, :, z]
        if sl.sum() < 50:
            continue
        v = hu[:, :, z][sl]
        lo, hi = np.percentile(v, [2, 98])
        core = v[(v >= lo) & (v <= hi)]
        if core.size < 30:
            continue
        sds.append(core.std())
        means.append(core.mean())
    if not sds:
        return float('nan'), float('nan')
    return float(np.median(sds)), float(np.median(means))


def vessel_rois(coronary_path):
    cb, _, _ = ctio.load_hu(coronary_path)
    vessel = cb > 0
    # perivascular shell: 2-4 voxel ring around the vessel, excluding the vessel
    d4 = ndi.binary_dilation(vessel, structure=np.ones((3, 3, 1), bool), iterations=4)
    d2 = ndi.binary_dilation(vessel, structure=np.ones((3, 3, 1), bool), iterations=2)
    peri = d4 & ~d2
    wall = ndi.binary_dilation(vessel, structure=np.ones((3, 3, 1), bool), iterations=1) & ~ndi.binary_erosion(
        vessel, structure=np.ones((3, 3, 1), bool))
    return vessel, peri, wall


def grad_mag(vol):
    gx = ndi.sobel(vol, axis=0)
    gy = ndi.sobel(vol, axis=1)
    return np.sqrt(gx * gx + gy * gy)


def metrics(hu, ref_hu, aorta, vessel, peri, wall):
    out = {}
    if aorta is not None:
        v = hu[aorta]
        sd, mu = robust_noise(hu, aorta)
        out['noise_sd'] = sd
        out['aorta_mean'] = mu
        out['snr'] = float(mu / sd) if sd > 0 else float('nan')
        out['fp130'] = int((v >= 130).sum())
        out['hu_bias'] = float(v.mean() - ref_hu[aorta].mean())
    else:
        sd = np.nan
        out.update(noise_sd=np.nan, aorta_mean=np.nan, snr=np.nan, fp130=-1, hu_bias=np.nan)

    out['vessel_mean'] = float(hu[vessel].mean())
    out['peri_mean'] = float(hu[peri].mean())
    out['cnr'] = float((hu[vessel].mean() - hu[peri].mean()) / sd) if sd == sd and sd > 0 else float('nan')
    out['cac130'] = int((hu[vessel] >= 130).sum())
    out['edge_grad'] = float(grad_mag(hu)[wall].mean())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='/mnt/raid2/amirg/Diff Models/work/selected_cases.json')
    ap.add_argument('--outputs', default='/mnt/raid2/amirg/Diff Models/work/outputs')
    ap.add_argument('--modalities', nargs='+', default=['ncct', 'ccta'])
    ap.add_argument('--erode', type=int, default=9)
    ap.add_argument('--json', default='/mnt/raid2/amirg/Diff Models/work/metrics.json')
    args = ap.parse_args()

    rows = []
    for rec in json.load(open(args.cases)):
        case = rec['case']
        p = ctio.case_paths(case)
        aorta = aorta_roi(p['aorta'], rec['shape'], erode=args.erode)
        vessel, peri, wall = vessel_rois(p['coronary'])
        print(f'{case}: aorta ROI {"n/a" if aorta is None else aorta.sum()} vox, '
              f'vessel {vessel.sum()} vox', flush=True)

        for mod in args.modalities:
            ref, _, _ = ctio.load_hu(p[mod])
            variants = {'original': ref}
            for m in MODELS:
                f = os.path.join(args.outputs, case, f'{mod}_{m}.nii.gz')
                if os.path.exists(f):
                    variants[m], _, _ = ctio.load_hu(f)
            for name, vol in variants.items():
                r = metrics(vol, ref, aorta, vessel, peri, wall)
                r.update(case=case, modality=mod, variant=name)
                rows.append(r)
                print(f'  {mod:5s} {name:10s} sd={r["noise_sd"]:7.2f} snr={r["snr"]:6.2f} '
                      f'cnr={r["cnr"]:6.2f} edge={r["edge_grad"]:7.1f} fp130={r["fp130"]:6d} '
                      f'bias={r["hu_bias"]:+.2f}', flush=True)

    json.dump(rows, open(args.json, 'w'), indent=1)
    print(f'\nwrote {len(rows)} rows -> {args.json}')


if __name__ == '__main__':
    main()
