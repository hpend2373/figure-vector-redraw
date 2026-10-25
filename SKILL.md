---
name: "sci-figure-vector-redraw"
description: "Turn a raster or AI-generated scientific concept figure into a corrected, editable 16:9 vector figure on a Design canvas using the user's traced SVG pieces: audit, layout math, asset slimming, review."
---

# Scientific concept figure -> corrected vector figure on a Design canvas

Use when the user shows a conceptual figure (often AI-generated; e.g. Input -> Deep-learning model -> Output pipelines) and wants it checked, vectorized and rebuilt as an editable figure.

## Working style for this user
- Reply in Korean, formal and concise: one-line outcome, details in bullets.
- Work in stages and wait for the go-ahead between them: audit -> text-only layout -> simple shapes -> user's real assets -> background/style -> alignment review. "일단 확인만" means audit only, build nothing.
- Fidelity to the original look is valued (background, text placement, panel titles). Keep scientific corrections anyway, and list anything you dropped so the user can restore it.
- If the user picks a notation that deviates from convention (e.g. W_i on GAT edges instead of alpha_ij), apply it and mention the convention once.

## Stage 1 - Scientific audit (before drawing)
Crop regions with PIL and inspect at 2x. Check:
- Duplicate or missing labels; count arrows vs reactions (AI images often draw 9 arrows for the 8 TCA steps and duplicate a label such as Succinate).
- Cluster plots: one label per cluster/colour, no unlabeled clusters, axes present.
- Notation: in a GAT the edge-specific values are attention coefficients alpha_ij; W is the shared weight matrix; GAT is a kind of GNN, so two side-by-side panels need a stated relationship.
- Claims vs encoding: "flux" needs stoichiometric constraints (S v = 0) or it is "pathway activity"; "spatially resolved" needs a spatial output (tissue map), not only a coloured cycle.
- Biology sanity (e.g. cortical Layer I is neuron-sparse).
- Typography: no hyphen after -ly adverbs ("spatially resolved").
- Generative-AI watermarks (corner sparkle): never reproduce; journals restrict generative images.
- Prior art via PubMed (e.g. scFEA, Genome Res 2021, https://doi.org/10.1101/gr.271205.120); cite with DOI.
Deliver a table (location / problem / fix) plus the open decisions.

## Stage 2 - Canvas and text layout (16:9)
- Artboard 1920x1080, Arial/Helvetica. Reuse the user's artboard; resize it via canvas.json.
- Grid: margins 64; columns a 64-624, b 704-1224, c 1304-1856; the 80px gaps hold the flow arrows.
- Rows: column headers top 52 (32px bold, centred over the column); cards 108-968; figure title at the bottom, top 990 (26px bold, centred, allowed to wrap).
- Type scale, keep to it: headers 32 / figure title 26 / panel titles 21 bold / labels and captions 16 / auxiliary 13. Ring-centre labels 24-28 bold. Same-level titles share the same top line per row.
- Undecided terminology -> a data-props enum tweak (e.g. outputTerm: Pathway activity / Metabolic flux) feeding holes in the titles.
- Measure text before placing it (Liberation Sans has Arial metrics):
  ```python
  from PIL import ImageFont
  f = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 16)
  f.getlength('α-Ketoglutarate')   # ~110 px
  ```
- Every text box stays inside its card (inner padding >= 16) and inside the 64px margins.

### Labels around a ring (TCA cycle)
- Ring centre and radius from the non-background bbox of a render of the asset.
- Anchor each label at R = visual radius + 14 at its angle. Right side: left-aligned starting at anchor + 4. Left side: right-aligned ending at anchor - 4. Top/bottom: centred.
- Centre the ring+labels group in the card. If the ring itself must sit on the card axis, move long labels (α-Ketoglutarate) to steeper angles until they fit.

### Labels on graph edges
- Edge midpoint + perpendicular offset >= half label width + 4 from the line. Check against other edges at that height, node discs and other label boxes.
- Plain text only (no background pills), 12px, W<sub>n</sub>; number all edges in a readable order; a drawn double (bidirectional) line counts as one edge unless asked.

## Stage 3 - The user's traced SVG assets
Typical input: vectorizer output with a <mask> alpha layer and 30k-350k paths ("M x y C ... Z" with translate()), 0.5-32 MB.
1. Unzip each archive into its own new folder; never run anything from inside it.
2. Render with Chromium/Playwright, not cairosvg (masks come out as colour speckle).
3. Design asset upload limit: 2 MB per file; the server inflates files ~10-13% -> aim for <= 1.5 MB locally.
4. svgo config: `{multipass:false, floatPrecision:1, plugins:[{name:'preset-default', params:{overrides:{cleanupIds:false, mergePaths:false}}}]}` -> about 4-5x smaller.
   svgo is superlinear: files > 15 MB can run 30+ min. Split the raw file first into ~8 MB pieces that each keep the full head (incl. mask), svgo the pieces (2 in parallel), then merge their bodies under one head.
5. Still > 1.5 MB -> chunk: same head (with mask) + consecutive body paths up to the budget per file. Stack the chunks as multiple background-image layers on ONE div (url() only inside a <helmet><style> rule; first url = top layer = last chunk). Confirm the recombination with a local render.
6. Removing junk (decorative icons): delete paths whose absolute bbox (translate + coords) lies fully inside the icon box, in both mask and visible layers; hide leftover halos by appending black ellipses inside the mask group.
7. Pixel-grid data images (spatial transcriptomics): re-vectorize instead of shipping the trace. Chromium render at 2x -> median colour per 1x pixel -> quantize (~48 colours) -> one path per colour of run-length rects `M x y h w v1 h-w z`, `shape-rendering="crispEdges"` (11.7 MB -> 0.37 MB). Repair artifacts (white notches) by vertical interpolation. Derived illustrative maps (e.g. neuron = expression, astrocyte = blurred inverse) must be marked illustrative.
8. vtracer cannot keep smooth gradients under 2 MB (swirls collapse to one colour); use the chunked original instead.
9. Art cut off at the image edge (e.g. half clusters at the top): do not fade it (a fade makes neighbouring elements look cut too). Complete it: duplicate the art div with `transform: scaleY(-1)` and `mask-image: radial-gradient(circle 42px at X Y, #000 34px, transparent 42px)` around a similar intact element, positioned so that element lands on the cut one.

## Stage 4 - Background and cards (original-look style)
- One decorative <svg aria-hidden> first in the root: radial gradient (#fff centre -> #dbe2ea edge); 1.5px traces #a3afb8 and #c5ced6 with 45-degree bends; filled pads r ~5; 2x5 square-pad grids; ghost rects #d4dbe2; barcode stripes; short blurred streaks (feGaussianBlur 5 x 1.6).
- Spread the motif across the whole figure (top band, bottom band, every gap), but only in margins and gaps between cards: inside cards traces read as stray dividers. Keep traces clear of every text box.
- Cards: input rgba(244,246,248,.74), 1.5px #c2cbd3, radius 18, shadow 0 6px 18px rgba(40,60,80,.07); model cards darker rgba(225,231,236,.8) with #b8c3cc; output card lighter rgba(248,250,251,.82). Every column needs a card or it melts into the background.
- Plot frames 1px #9aa4ad (not black). Flow arrows sit at the vertical centre of the cards they connect.

## Stage 5 - Review loop
Build a local preview: take the fragment between <x-dc> and </x-dc>, drop the <helmet> tags, replace /_blob/<id> with local files (keep a blob-id -> local-file map from every upload), fill the holes, render 1920x1080 at 1x and 2x, crop each card. Check: text clipped at the right edge, one centre axis per card (title, maps, ring), equal vertical gaps, legend not glued to the card bottom, stray background pieces, label overlaps. Report findings ranked by importance; apply them once the user agrees.

## Canvas etiquette
- Re-read the artboard before each publish whenever the user may have edited (view-context `edits` / `dirty`). If a publish result says a page-saved version was replaced, tell the user which file was overwritten and offer to re-apply their edits.
- Comment threads: resolve the anchor `#tid:path` by parsing the fragment (every tag counts, svg children included), make the change, reply in the thread, then resolve it.
## Helper scripts (scripts/ in this repo)
- `svgo.config.cjs` - svgo settings that keep mask ids and path order (Stage 3, step 4).
- `svg_split.py` - cut a traced SVG into pieces that each keep the mask: `--pieces N` before svgo, `--max-bytes 1500000` for upload chunks (Stage 3, steps 4-5).
- `svg_merge.py` - merge svgo-optimised pieces back into one file.
- `svg_remove_boxes.py` - drop icon paths by bbox, remove light halos, add black mask ellipses (Stage 3, step 6).
- `grid_revectorize.py` - spot-grid maps to run-length rect SVGs, artefact repair, illustrative derived maps (Stage 3, step 7).
- `measure_text.py`, `ring_labels.py` - Arial-metric text widths and label boxes around a ring (Stage 2).
- `build_preview.py` + `render.js` - standalone preview of an artboard and Chromium renders of SVGs, stacked chunks and pages (Stages 3 and 5).
