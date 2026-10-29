"""CoreDiff inference on MIHEART paired volumes.

Loads the released Mayo-2016 25%-dose checkpoint (ema_model-150000) into the
CoreDiff Diffusion wrapper and denoises each axial slice using the 3-slice
context the model was trained with.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch

REPO = '/mnt/raid2/amirg/Diff Models/repos/CoreDiff'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import ctio

def _load(name, relpath):
    """Import a CoreDiff module directly by path.

    models/__init__.py imports the full training task (wandb, perceptual loss),
    none of which is needed for inference, so we bypass the package.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


Network = _load('cd_wrapper', 'models/corediff/corediff_wrapper.py').Network
Diffusion = _load('cd_diffusion', 'models/corediff/diffusion_modules.py').Diffusion

CKPT = '/mnt/raid2/amirg/Diff Models/weights/CoreDiff/ema_model-150000'


def build_model(device):
    denoise_fn = Network(in_channels=3, out_channels=1, context=True)
    model = Diffusion(denoise_fn=denoise_fn, image_size=512, timesteps=10,
                      context=True).to(device)
    sd = torch.load(CKPT, map_location='cpu', weights_only=False)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    assert not [k for k in missing if 'denoise_fn' in k], f'missing: {missing[:5]}'
    print(f'[corediff] loaded {CKPT}  missing={len(missing)} unexpected={len(unexpected)}')
    model.eval()
    return model


@torch.no_grad()
def denoise_volume(model, hu, device, batch=8, t=10, n_iter=150000,
                   start_adjust_iter=1, z0=None, z1=None):
    unit = ctio.to_unit(hu, 'corediff')
    nz = unit.shape[2]
    z0 = 0 if z0 is None else max(0, z0)
    z1 = nz if z1 is None else min(nz, z1)
    out = unit.copy()

    zs = list(range(z0, z1))
    for i in range(0, len(zs), batch):
        chunk = zs[i:i + batch]
        x = np.stack([ctio.context_stack(unit, z) for z in chunk], axis=0)
        x = torch.from_numpy(x).float().to(device)
        gen, _, _ = model.sample(batch_size=x.shape[0], img=x, t=t,
                                 sampling_routine='ddim', n_iter=n_iter,
                                 start_adjust_iter=start_adjust_iter)
        gen = gen[:, 0].clamp(0, 1).cpu().numpy()
        for j, z in enumerate(chunk):
            out[:, :, z] = gen[j]
    return ctio.to_hu(out, 'corediff')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='/mnt/raid2/amirg/Diff Models/work/selected_cases.json')
    ap.add_argument('--out', default='/mnt/raid2/amirg/Diff Models/work/outputs')
    ap.add_argument('--modalities', nargs='+', default=['ncct', 'ccta'])
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--cardiac_only', action='store_true',
                    help='only run slices spanning the coronary mask (+margin)')
    ap.add_argument('--margin', type=int, default=12)
    args = ap.parse_args()

    device = 'cuda'
    model = build_model(device)
    cases = json.load(open(args.cases))
    if args.limit:
        cases = cases[:args.limit]

    for rec in cases:
        case = rec['case']
        paths = ctio.case_paths(case)
        z0 = z1 = None
        if args.cardiac_only:
            z0 = max(0, rec['z_min'] - args.margin)
            z1 = min(rec['shape'][2], rec['z_max'] + args.margin + 1)
        for mod in args.modalities:
            dst = os.path.join(args.out, case, f'{mod}_corediff.nii.gz')
            if os.path.exists(dst):
                print(f'[corediff] skip existing {dst}')
                continue
            hu, aff, hdr = ctio.load_hu(paths[mod])
            t0 = time.time()
            den = denoise_volume(model, hu, device, batch=args.batch, z0=z0, z1=z1)
            ctio.save_like(dst, den, aff, hdr)
            print(f'[corediff] {case} {mod} {hu.shape} '
                  f'z=[{z0},{z1}] {time.time() - t0:.1f}s -> {dst}', flush=True)


if __name__ == '__main__':
    main()
