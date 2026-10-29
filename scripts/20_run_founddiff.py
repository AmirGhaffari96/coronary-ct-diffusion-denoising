"""FoundDiff inference on MIHEART paired volumes.

Builds the residual-diffusion UNet (Mamba blocks + DA-CLIP dose encoder) used by
FoundDiff, loads the released EMA weights from model-400.pt, and denoises each
axial slice. The repo's own train.py cannot be used for this: it references an
undefined `folder` variable and hard-codes Mayo .npy paths, so we drive the
model directly.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch

REPO = '/mnt/raid2/amirg/Diff Models/repos/FoundDiff'
HERE = os.path.dirname(os.path.abspath(__file__))
CKPT = '/mnt/raid2/amirg/Diff Models/weights/FoundDiff/model-400.pt'

# DADiff.py does torch.load('Dose-CLIP.pth') with a relative path, and imports
# repo-relative packages, so the repo must be the cwd and on sys.path.
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import ctio
from src.DADiff import ResidualDiffusion, UnetRes


def build_model(device, sampling_timesteps=2):
    model = UnetRes(dim=64, dim_mults=(1, 2, 4, 8), num_unet=1,
                    condition=True, input_condition=False,
                    objective='pred_res', test_res_or_noise='res')
    diffusion = ResidualDiffusion(
        model, image_size=512, timesteps=1000,
        sampling_timesteps=sampling_timesteps, objective='pred_res',
        loss_type='l2', condition=True, sum_scale=0.01,
        input_condition=False, input_condition_mask=False,
        test_res_or_noise='res',
    )
    data = torch.load(CKPT, map_location='cpu', weights_only=False)
    ema_sd = {k[len('ema_model.'):]: v for k, v in data['ema'].items()
              if k.startswith('ema_model.')}
    missing, unexpected = diffusion.load_state_dict(ema_sd, strict=False)
    hard = [k for k in missing if k.startswith('model.')]
    assert not hard, f'unloaded UNet weights: {hard[:5]}'
    print(f'[founddiff] loaded EMA @ step {data["step"]} '
          f'({len(ema_sd)} tensors, missing={len(missing)}, unexpected={len(unexpected)})')
    diffusion = diffusion.to(device).eval()
    diffusion.init()          # rebuild the DDIM-converted schedule, as trainer.test() does
    diffusion = diffusion.to(device)
    return diffusion


@torch.no_grad()
def denoise_volume(diffusion, hu, device, batch=4, z0=None, z1=None):
    unit = ctio.to_unit(hu, 'founddiff')
    nz = unit.shape[2]
    z0 = 0 if z0 is None else max(0, z0)
    z1 = nz if z1 is None else min(nz, z1)
    out = unit.copy()

    zs = list(range(z0, z1))
    for i in range(0, len(zs), batch):
        chunk = zs[i:i + batch]
        x = np.stack([unit[:, :, z][None] for z in chunk], axis=0)   # (B,1,H,W)
        x = torch.from_numpy(x).float().to(device)
        pred = diffusion.sample([x], batch_size=x.shape[0], last=True)[-1]
        pred = pred[:, 0].clamp(0, 1).float().cpu().numpy()
        for j, z in enumerate(chunk):
            out[:, :, z] = pred[j]
    return ctio.to_hu(out, 'founddiff')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='/mnt/raid2/amirg/Diff Models/work/selected_cases.json')
    ap.add_argument('--out', default='/mnt/raid2/amirg/Diff Models/work/outputs')
    ap.add_argument('--modalities', nargs='+', default=['ncct', 'ccta'])
    ap.add_argument('--batch', type=int, default=4)
    ap.add_argument('--sampling_timesteps', type=int, default=2)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--cardiac_only', action='store_true')
    ap.add_argument('--margin', type=int, default=12)
    args = ap.parse_args()

    device = 'cuda'
    diffusion = build_model(device, args.sampling_timesteps)
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
            dst = os.path.join(args.out, case, f'{mod}_founddiff.nii.gz')
            if os.path.exists(dst):
                print(f'[founddiff] skip existing {dst}')
                continue
            hu, aff, hdr = ctio.load_hu(paths[mod])
            t0 = time.time()
            den = denoise_volume(diffusion, hu, device, batch=args.batch, z0=z0, z1=z1)
            ctio.save_like(dst, den, aff, hdr)
            print(f'[founddiff] {case} {mod} {hu.shape} '
                  f'z=[{z0},{z1}] {time.time() - t0:.1f}s -> {dst}', flush=True)


if __name__ == '__main__':
    main()
