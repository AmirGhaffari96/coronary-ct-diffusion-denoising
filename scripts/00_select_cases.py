"""Screen MIHEART_REG_PAIRED_BATCH3 and select 10 paired NCCT/CCTA cases.

Selection criteria (all must hold):
  - img.nii.gz, regCCTA_*.nii.gz and coronary_branches.nii.gz present, identical
    512x512xZ grid and affine (already registered)
  - all 4 coronary branch labels present
  - coronary mask volume large enough to give a stable ROI statistic
Ranking: by coronary mask volume (descending) so the vessel ROI is well populated,
then take a spread across the ranked list so we do not only pick one extreme.
"""
import os, glob, json
import numpy as np
import nibabel as nib

ROOT = '/home/amirg/mnt/raid2/chenyu/MIHEART_REG_PAIRED_BATCH3'
OUT = '/mnt/raid2/amirg/Diff Models/work'
N_SELECT = 10

rows = []
for case in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, case)
    img_p = os.path.join(d, 'img.nii.gz')
    cta_g = glob.glob(os.path.join(d, 'regCCTA_*.nii.gz'))
    cb_p = os.path.join(d, 'coronary_branches.nii.gz')
    if not (os.path.exists(img_p) and cta_g and os.path.exists(cb_p)):
        continue
    cta_p = cta_g[0]
    try:
        a, b, m = nib.load(img_p), nib.load(cta_p), nib.load(cb_p)
    except Exception:
        continue
    if a.shape != b.shape or a.shape != m.shape or a.shape[:2] != (512, 512):
        continue
    if not np.allclose(a.affine, b.affine, atol=1e-3):
        continue

    cb = np.asarray(m.dataobj)
    labels = np.unique(cb)
    labels = labels[labels > 0]
    if len(labels) < 4:
        continue
    nvox = int((cb > 0).sum())
    zs = np.where((cb > 0).any(axis=(0, 1)))[0]

    rows.append(dict(
        case=case, cta=os.path.basename(cta_p),
        shape=[int(v) for v in a.shape],
        zooms=[float(v) for v in a.header.get_zooms()],
        coronary_vox=nvox, n_labels=int(len(labels)),
        z_min=int(zs.min()), z_max=int(zs.max()),
    ))

rows.sort(key=lambda r: -r['coronary_vox'])
# spread over the top half of the ranked list for variety in anatomy/size
pool = rows[:max(N_SELECT, len(rows) // 2)]
idx = np.linspace(0, len(pool) - 1, N_SELECT).round().astype(int)
sel = [pool[i] for i in idx]

os.makedirs(OUT, exist_ok=True)
json.dump(rows, open(os.path.join(OUT, 'all_cases.json'), 'w'), indent=1)
json.dump(sel, open(os.path.join(OUT, 'selected_cases.json'), 'w'), indent=1)

print(f'screened {len(rows)} eligible cases')
print(f'{"case":<16}{"vox":>8}{"Z":>6}  z-range      shape')
for r in sel:
    print(f'{r["case"]:<16}{r["coronary_vox"]:>8}{r["shape"][2]:>6}  '
          f'{r["z_min"]:>3}-{r["z_max"]:<4}  {r["shape"]}')
