"""Comparison figures: original vs CoreDiff vs FoundDiff, for both modalities.

For each case we pick the axial slice carrying the most coronary voxels and
render it, plus a zoomed crop centred on the coronary centroid so the vessel
itself is actually legible. Four rows: non-contrast full and zoom, then CCTA
full and zoom, each showing original / CoreDiff / FoundDiff side by side.

Each modality is rendered in its own window — contrast-filled lumen sits far
above non-contrast tissue, so one shared window would make one or the other
unreadable.

These figures are patient images: they render real anatomy, and the default
title carries the accession ID. Pass --anonymise to title by index instead.
Either way they are gitignored and must never be committed.
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
    ap.add_argument('--anonymise', action='store_true',
                    help='title and name figures by index rather than accession ID')
    args = ap.parse_args()
    os.makedirs(args.figdir, exist_ok=True)

    for idx, rec in enumerate(json.load(open(args.cases)), start=1):
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

        # one row-pair (full + zoom) per modality, variants across the columns
        per_mod = {mod: ['original'] + [m for m in MODELS if (mod, m) in vols]
                   for mod in ['ncct', 'ccta']}
        ncol = max(len(v) for v in per_mod.values())
        fig, axes = plt.subplots(4, ncol, figsize=(3.0 * ncol, 12.6),
                                 squeeze=False)
        mask = cb[y0:y1, x0:x1, z] > 0

        for r0, mod in ((0, 'ncct'), (2, 'ccta')):
            tag = 'NCCT' if mod == 'ncct' else 'CCTA'
            for c in range(ncol):
                if c >= len(per_mod[mod]):
                    axes[r0, c].axis('off')
                    axes[r0 + 1, c].axis('off')
                    continue
                var = per_mod[mod][c]
                im = vols[(mod, var)]
                show(axes[r0, c], im, WIN[mod], f'{tag} · {LABEL[var]}')
                show(axes[r0 + 1, c], im[y0:y1, x0:x1], WIN[mod],
                     f'zoom · {tag} {LABEL[var]}')
                # outline the coronary mask on the zoom panels
                axes[r0 + 1, c].contour(mask.T.astype(float), levels=[0.5],
                                        colors='#ff3b30', linewidths=0.7)

        name = f'case-{idx:02d}' if args.anonymise else case
        fig.suptitle(f'{name} — axial z={z}   ·   NCCT window '
                     f'{WIN["ncct"][0]}..{WIN["ncct"][1]} HU   ·   CCTA window '
                     f'{WIN["ccta"][0]}..{WIN["ccta"][1]} HU', fontsize=11)
        fig.tight_layout(rect=[0, 0, 1, 0.975])
        dst = os.path.join(args.figdir, f'{name}_compare.png')
        fig.savefig(dst, dpi=150)
        plt.close(fig)
        print(f'{case}: z={z} -> {dst}', flush=True)


if __name__ == '__main__':
    main()
