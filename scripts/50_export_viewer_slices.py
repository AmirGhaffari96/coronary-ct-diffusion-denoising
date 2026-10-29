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

# vCCTA_V6: synthetic contrast CT predicted from the non-contrast scan, and the
# same prediction with CCTA-like noise grain added. Baked in the 'ccta' range
# because that is the HU distribution they imitate.
VCCTA_PANELS = [
    ('vccta',     '_vCCTA.nii.gz'),
    ('vccta_tex', '_vCCTA_textured.nii.gz'),
]
VCCTA_DIRS = [
    '/mnt/raid2/amirg/vCCTA_V6/results/eval_final_test/nifti',   # the 100 hold-out cases
    '/mnt/raid2/amirg/Diff Models/work/vccta',                   # generated for the rest
]
VCCTA_SPLIT = '/mnt/raid2/amirg/vCCTA_V6/results/split.json'


def vccta_path(case, suffix, dirs):
    for d in dirs:
        f = os.path.join(d, f'{case}{suffix}')
        if os.path.exists(f):
            return f
    return None


def load_split(path):
    """case -> 'train' | 'val' | 'test'.

    Which split a case fell in decides what a vCCTA panel is allowed to claim:
    on a training case the model has seen the answer, so the panel shows
    memorisation, not performance. The viewer badges this per case.
    """
    try:
        d = json.load(open(path))
    except Exception:
        return {}
    out = {}
    for k, v in d.items():
        if not isinstance(v, list):
            continue
        for e in v:
            name = e if isinstance(e, str) else (e.get('case') or e.get('id') or '')
            out[str(name).rstrip('/').split('/')[-1]] = k
    return out


def to_u8(hu, lo, hi):
    return np.clip((hu - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='/mnt/raid2/amirg/Diff Models/work/selected_cases.json')
    ap.add_argument('--outputs', default='/mnt/raid2/amirg/Diff Models/work/outputs')
    ap.add_argument('--dst', default='/mnt/raid2/amirg/Diff Models/viewer/slices')
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--quality', type=int, default=85)
    ap.add_argument('--vccta-dirs', nargs='*', default=VCCTA_DIRS)
    ap.add_argument('--vccta-split', default=VCCTA_SPLIT)
    args = ap.parse_args()

    split = load_split(args.vccta_split)
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

        # vCCTA_V6 panels, when a prediction exists for this case
        for name, suffix in VCCTA_PANELS:
            f = vccta_path(case, suffix, args.vccta_dirs)
            if f is None:
                continue
            vol, _, _ = ctio.load_hu(f)
            if vol.shape != base['ncct'].shape:
                print(f'  !! {name}: shape {vol.shape} != {base["ncct"].shape}, skipped',
                      flush=True)
                continue
            lo, hi = BAKE['ccta']
            d = os.path.join(args.dst, case, name)
            os.makedirs(d, exist_ok=True)
            for z in range(z0, z1):
                sl = to_u8(vol[:, :, z], lo, hi).T[::-1]
                Image.fromarray(sl).save(os.path.join(d, f'{z:04d}.jpg'),
                                         quality=args.quality, optimize=True)
            avail.append(dict(name=name, modality='vccta',
                              model='textured' if name.endswith('_tex') else 'plain',
                              kind='ccta'))

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
                                      zooms=rec['zooms'], panels=avail,
                                      vccta_split=split.get(case, 'not in split')))
        print(f'{case}: z {z0}-{z1 - 1} ({z1 - z0} slices) x {len(avail)} panels', flush=True)

    os.makedirs(os.path.dirname(args.dst), exist_ok=True)
    json.dump(manifest, open(os.path.join(os.path.dirname(args.dst), 'manifest.json'), 'w'), indent=1)
    print('manifest written')


if __name__ == '__main__':
    main()
