"""Shared CT volume IO / normalization helpers for the diffusion denoisers.

Each upstream repo has its own HU->[0,1] convention; we keep them explicit here
so the same volume can be fed to every model without silently mismatching the
range the network was trained on.

  CoreDiff  : HU clipped to [-1024, 3072], x = (HU + 1024) / 4096
  FoundDiff : HU clipped to [-1000, 2000], x = (HU + 1000) / 3000
"""
import glob
import os

import nibabel as nib
import numpy as np

ROOT = '/home/amirg/mnt/raid2/chenyu/MIHEART_REG_PAIRED_BATCH3'

NORM = {
    'corediff':  dict(lo=-1024.0, hi=3072.0),
    'founddiff': dict(lo=-1000.0, hi=2000.0),
}


def case_paths(case):
    d = os.path.join(ROOT, case)
    cta = sorted(glob.glob(os.path.join(d, 'regCCTA_*.nii.gz')))[0]
    return dict(
        ncct=os.path.join(d, 'img.nii.gz'),
        ccta=cta,
        coronary=os.path.join(d, 'coronary_branches.nii.gz'),
        heart=os.path.join(d, 'whole_heart.nii.gz'),
        aorta=os.path.join(d, 'ai_cac_aorta_calibration_seg.nii.gz'),
    )


def load_hu(path):
    im = nib.load(path)
    return np.asarray(im.dataobj, dtype=np.float32), im.affine, im.header


def to_unit(hu, model):
    lo, hi = NORM[model]['lo'], NORM[model]['hi']
    return (np.clip(hu, lo, hi) - lo) / (hi - lo)


def to_hu(unit, model):
    lo, hi = NORM[model]['lo'], NORM[model]['hi']
    return unit * (hi - lo) + lo


def save_like(path, data_hu, affine, header):
    """Write HU volume as float32 NIfTI reusing the source geometry."""
    hdr = header.copy()
    hdr.set_data_dtype(np.float32)
    hdr['scl_slope'] = 1.0
    hdr['scl_inter'] = 0.0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nib.save(nib.Nifti1Image(data_hu.astype(np.float32), affine, hdr), path)


def context_stack(vol_unit, z):
    """(3, H, W) neighbourhood [z-1, z, z+1] with edge replication."""
    nz = vol_unit.shape[2]
    zs = [max(0, z - 1), z, min(nz - 1, z + 1)]
    return np.stack([vol_unit[:, :, i] for i in zs], axis=0)
