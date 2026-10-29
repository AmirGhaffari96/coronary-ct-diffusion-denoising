"""Export windowed JPEG slice stacks for the web viewer.

Each (case, panel) axial stack is written as 8-bit JPEGs baked at a WIDE window.
The viewer then applies the user's window/level as an exact linear remap through
CSS contrast/brightness, so interactive W/L stays GPU-fast and still faithful to
HU within the baked range.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctio

# baked ranges (HU) — chosen wide enough to cover any window a reader will pick
BAKE = dict(ncct=(-300.0, 700.0), ccta=(-300.0, 1100.0), diff=(-60.0, 60.0))

PANELS = [
    ('ncct_original',   'ncct', None,        'ncct'),
    ('ncct_corediff',   'ncct', 'corediff',  'ncct'),
    ('ncct_founddiff',  'ncct', 'founddiff', 'ncct'),
    ('ccta_original',   'ccta', None,        'ccta'),
    ('ccta_corediff',   'ccta', 'corediff',  'ccta'),
    ('ccta_founddiff',  'ccta', 'founddiff', 'ccta'),
    ('ncct_diff_corediff',  'ncct', 'corediff',  'diff'),
    ('ncct_diff_founddiff', 'ncct', 'founddiff', 'diff'),
]


def to_u8(hu, lo, hi):
    return np.clip((hu - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='/mnt/raid2/amirg/Diff Models/work/selected_cases.json')
    ap.add_argument('--outputs', default='/mnt/raid2/amirg/Diff Models/work/outputs')
    ap.add_argument('--dst', default='/mnt/raid2/amirg/Diff Models/viewer/slices')
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--quality', type=int, default=85)
    args = ap.parse_args()

    manifest = dict(bake={k: list(v) for k, v in BAKE.items()}, cases=[])

    for rec in json.load(open(args.cases)):
        case = rec['case']
        p = ctio.case_paths(case)
        nz = rec['shape'][2]
        z0 = max(0, rec['z_min'] - args.margin)
        z1 = min(nz, rec['z_max'] + args.margin + 1)

        base = {}
        for mod in ('ncct', 'ccta'):
            base[mod], _, _ = ctio.load_hu(p[mod])
        den = {}
        for mod in ('ncct', 'ccta'):
            for m in ('corediff', 'founddiff'):
                f = os.path.join(args.outputs, case, f'{mod}_{m}.nii.gz')
                if os.path.exists(f):
                    den[(mod, m)], _, _ = ctio.load_hu(f)

        cb, _, _ = ctio.load_hu(p['coronary'])

        avail = []
        for name, mod, model, kind in PANELS:
            if model is not None and (mod, model) not in den:
                continue
            src = base[mod] if model is None else den[(mod, model)]
            if kind == 'diff':
                src = src - base[mod]
            lo, hi = BAKE[kind]
            d = os.path.join(args.dst, case, name)
            os.makedirs(d, exist_ok=True)
            for z in range(z0, z1):
                # transpose+flip so the JPEG is in radiological display order
                sl = to_u8(src[:, :, z], lo, hi).T[::-1]
                Image.fromarray(sl).save(os.path.join(d, f'{z:04d}.jpg'),
                                         quality=args.quality, optimize=True)
            avail.append(dict(name=name, modality=mod, model=model or 'original', kind=kind))

        # coronary mask overlay as a transparent PNG per slice
        d = os.path.join(args.dst, case, 'mask')
        os.makedirs(d, exist_ok=True)
        for z in range(z0, z1):
            m = (cb[:, :, z] > 0).T[::-1]
            rgba = np.zeros((*m.shape, 4), np.uint8)
            rgba[m] = (255, 59, 48, 110)
            Image.fromarray(rgba, 'RGBA').save(os.path.join(d, f'{z:04d}.png'), optimize=True)

        manifest['cases'].append(dict(case=case, z0=z0, z1=z1, nz=nz,
                                      z_min=rec['z_min'], z_max=rec['z_max'],
                                      zooms=rec['zooms'], panels=avail))
        print(f'{case}: z {z0}-{z1 - 1} ({z1 - z0} slices) x {len(avail)} panels', flush=True)

    os.makedirs(os.path.dirname(args.dst), exist_ok=True)
    json.dump(manifest, open(os.path.join(os.path.dirname(args.dst), 'manifest.json'), 'w'), indent=1)
    print('manifest written')


if __name__ == '__main__':
    main()
