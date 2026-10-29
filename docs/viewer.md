# Viewer

A dependency-free web viewer for stepping through the denoised volumes side by
side. One slice index drives every panel, so the comparison is always of the
same anatomy.

```bash
./scripts/serve_viewer.sh
```

then open <http://localhost:8712>.

## Access

The server binds **127.0.0.1 only**, deliberately. These are patient images and
the server has no authentication of any kind. From another machine, tunnel in
rather than changing the bind address:

```bash
ssh -L 8712:localhost:8712 <user>@<host>
```

and open <http://localhost:8712> locally. See
[data-and-privacy.md](data-and-privacy.md).

## Panels

Nine panels, all toggled from the single **Panels** menu in the sidebar:

| panel | content |
|---|---|
| `ncct_original` / `ncct_corediff` / `ncct_founddiff` | the non-contrast scan, before and after each model |
| `ccta_original` / `ccta_corediff` / `ccta_founddiff` | the registered CCTA, same |
| `ncct_diff_corediff` / `ncct_diff_founddiff` | original − denoised, i.e. **what the model removed** |
| `swipe` | two panels in one cell, split by a draggable divider (see below) |

The default set is the three NCCT panels plus `swipe`. CCTA panels are
available but off by default — the non-contrast scan is what these models are
for, so it earns the default real estate.

The difference panels are the most diagnostic of the set. A good denoiser's
difference image should look like structureless noise. Visible vessel outlines
in it mean anatomy is being removed, not noise.

## Before / after swipe

`swipe` is a panel like any other: tick it and it takes one cell in the grid,
alongside the ordinary panels, holding two registered layers split by a
draggable divider. It is the clearest way to see what changed at a given point,
and because it is just a cell you can keep the single-panel views beside it.

Its settings live directly under the panel list, and appear only while the
panel is ticked.

- pick the **before** and **after** layers independently (any two of the other
  eight panels — including CCTA vs NCCT, or one model against the other)
- **drag the blue divider** to wipe across; or use the `divider` slider
- **double-click the divider** to recentre it at 50%
- the HU readout reports the layer on the side the cursor is actually over,
  not whichever one happens to be underneath

Both layers share one pan/zoom transform, so they never drift out of
registration — only the clip of the top layer moves.

## Controls

| input | action |
|---|---|
| wheel | scroll slices |
| ctrl / ⌘ + wheel | zoom at cursor |
| drag | pan (all panels together) |
| ← / → / ↑ / ↓ | step one slice |
| space | cine loop |
| hover | HU readout at the cursor |

Window/level presets (cardiac, mediastinum, calcium, soft tissue) plus free
width/level sliders. CCTA gets a separate **level offset** (default +200 HU)
because contrast-filled lumen sits much higher than non-contrast tissue; one
shared level would make one or the other unreadable.

The coronary mask overlays in red; grayscale can be inverted.

## Linkable state

Everything lives in the URL, so a specific finding can be sent to someone else:

```
?case=<CASE-ID>&z=150&panels=ncct_original,ncct_founddiff
&w=600&l=100&mask=1&sa=ncct_original&sb=ncct_founddiff&sx=50
```

| key | meaning |
|---|---|
| `case`, `z` | case and slice index |
| `panels` | comma-separated active panels, `swipe` included |
| `w`, `l` | window width / level |
| `mask` | coronary mask overlay on |
| `sa`, `sb` | the swipe panel's before / after layers |
| `sx` | divider position, percent |

## How it renders

Slices are pre-baked to 8-bit JPEG by `50_export_viewer_slices.py` at a fixed
window per kind (`manifest.json → bake`: NCCT [−300, 700], CCTA [−300, 1100],
difference [−60, 60]). Interactive window/level is then an exact linear remap
of that baked range, done in CSS:

```
baked    v   = (HU − lo) / (hi − lo)
desired  out = (HU − (L − W/2)) / W
       → out = a·v + d,  a = (hi−lo)/W,  d = (lo − L + W/2)/W
CSS contrast(C) brightness(B):  out = B·((v−0.5)·C + 0.5)
       → B = 2d + a,  C = a/B
```

This is why the viewer needs no WebGL and no NIfTI decoding in the browser —
but also why HU below the baked floor or above its ceiling are clipped and
cannot be recovered by moving the sliders. The readout reports HU inferred back
from the baked range, so it is accurate to roughly ±4 HU on NCCT, not exact.

On case load the viewer preloads every slice of every active panel (24
concurrent requests, progress bar). That is why the server is threaded — a
single-threaded `http.server` serialises the ~800 requests and makes loading
crawl.
