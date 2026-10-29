"""Comparison figures: original vs CoreDiff vs FoundDiff, with CCTA reference.

For each case we pick the axial slice carrying the most coronary voxels and
render it in a cardiac window, plus a zoomed crop centred on the coronary
centroid so the vessel itself is actually legible.
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctio

WIN = dict(ncct=(-100, 300), ccta=(-100, 700))   # (level-range) display windows
MODELS = ['corediff', 'founddiff']
LABEL = dict(original='Original', corediff='CoreDiff', founddiff='FoundDiff')


def show(ax, img, win, title):
    ax.imshow(img.T, cmap='gray', vmin=win[0], vmax=win[1], origin='lower')
    ax.set_title(title, fontsize=9)
    ax.axis('off')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='/mnt/raid2/amirg/Diff Models/work/selected_cases.json')
    ap.add_argument('--outputs', default='/mnt/raid2/amirg/Diff Models/work/outputs')
    ap.add_argument('--figdir', default='/mnt/raid2/amirg/Diff Models/work/figures')
    ap.add_argument('--crop', type=int, default=140)
    args = ap.parse_args()
    os.makedirs(args.figdir, exist_ok=True)

    for rec in json.load(open(args.cases)):
        case = rec['case']
        p = ctio.case_paths(case)
        cb, _, _ = ctio.load_hu(p['coronary'])
        counts = (cb > 0).sum(axis=(0, 1))
        z = int(np.argmax(counts))
        ys, xs = np.where(cb[:, :, z] > 0)
        cy, cx = int(ys.mean()), int(xs.mean())
        h = args.crop // 2
        y0, y1 = max(0, cy - h), min(cb.shape[0], cy + h)
        x0, x1 = max(0, cx - h), min(cb.shape[1], cx + h)

        vols = {}
        for mod in ['ncct', 'ccta']:
            v, _, _ = ctio.load_hu(p[mod])
            vols[(mod, 'original')] = v[:, :, z]
            for m in MODELS:
                f = os.path.join(args.outputs, case, f'{mod}_{m}.nii.gz')
                if os.path.exists(f):
                    vv, _, _ = ctio.load_hu(f)
                    vols[(mod, m)] = vv[:, :, z]

        variants = ['original'] + [m for m in MODELS if ('ncct', m) in vols]
        ncol = len(variants) + 1                      # + CCTA reference column
        fig, axes = plt.subplots(2, ncol, figsize=(3.0 * ncol, 6.4))

        for c, var in enumerate(variants):
            im = vols[('ncct', var)]
            show(axes[0, c], im, WIN['ncct'], f'NCCT · {LABEL[var]}')
            show(axes[1, c], im[y0:y1, x0:x1], WIN['ncct'], f'zoom · {LABEL[var]}')
        ref = vols[('ccta', 'original')]
        show(axes[0, -1], ref, WIN['ccta'], 'CCTA reference')
        show(axes[1, -1], ref[y0:y1, x0:x1], WIN['ccta'], 'zoom · CCTA')
        # outline the coronary mask on the zoom panels
        mask = cb[y0:y1, x0:x1, z] > 0
        for c in range(ncol):
            axes[1, c].contour(mask.T.astype(float), levels=[0.5],
                               colors='#ff3b30', linewidths=0.7)

        fig.suptitle(f'{case} — axial z={z} (coronary window -100..300 HU)', fontsize=11)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        dst = os.path.join(args.figdir, f'{case}_ncct_compare.png')
        fig.savefig(dst, dpi=150)
        plt.close(fig)
        print(f'{case}: z={z} -> {dst}', flush=True)


if __name__ == '__main__':
    main()
