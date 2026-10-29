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
| `vccta` / `vccta_tex` | vCCTA v6 — synthetic contrast CT predicted from the non-contrast scan, plain and with CCTA-like noise grain |
| `swipe` | two panels in one cell, split by a draggable divider (see below) |

The default set is the three NCCT panels plus `swipe`. CCTA panels are
available but off by default — the non-contrast scan is what these models are
for, so it earns the default real estate.

The difference panels are the most diagnostic of the set. A good denoiser's
difference image should look like structureless noise. Visible vessel outlines
in it mean anatomy is being removed, not noise.

## vCCTA v6 panels, and the split badge

`vccta` and `vccta_tex` come from a different model entirely —
[vCCTA_V6](/mnt/raid2/amirg/vCCTA_V6), which **synthesises** contrast CT from
the non-contrast scan rather than denoising it. They are included so the two
approaches can be compared on the same slice: CoreDiff and FoundDiff clean up
the scan you have, vCCTA invents the scan you don't.

Both window with the CCTA sliders, since they imitate that HU distribution.

**The Case box shows which vCCTA_V6 split each case was in, and this matters
more than it looks:**

| badge | meaning |
|---|---|
| `held out` (green) | genuine held-out performance |
| `validation` (blue) | used for model selection |
| `TRAINING — model saw this case` (orange) | the model was fitted on this scan |
| `not in split` (grey) | excluded from vCCTA_V6, often by the registration-score cut |

Of the 10 cases here only **two** are held out. On a training case the vCCTA
panels show memorisation, not performance, and must not be read as evidence —
CoreDiff and FoundDiff never saw any of this data, so putting them side by side
on a training case is not a like-for-like comparison. The badge sits beside the
case selector rather than inside a panel so it stays visible whichever panels
are on.

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

**Non-contrast and CCTA carry independent window/level.** Contrast-filled
lumen sits far above non-contrast tissue, so a single shared window makes one
or the other unreadable. Each gets its own preset menu and its own width and
level sliders:

| | presets | default |
|---|---|---|
| non-contrast | cardiac, mediastinum, calcium, soft tissue | W600 L100 |
| CCTA | mediastinum, coronary, wide, calcium | W600 L300 |

`reset W/L` restores both. Difference panels are unaffected — they are baked at
a fixed ±60 HU and ignore both sets of sliders.

The coronary mask overlays in red; grayscale can be inverted.

## Linkable state

Everything lives in the URL, so a specific finding can be sent to someone else.

**A URL carrying `panels=` pins that panel set and overrides the defaults.** The
viewer writes your selection into the address bar as you work, so a link saved
before a panel existed will keep that panel switched off — in a private window
too, since the state is in the URL rather than the cache. The **defaults** and
**all** buttons above the panel list reset it; so does opening the viewer with
no query string at all.

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
