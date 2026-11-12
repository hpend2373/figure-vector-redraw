---
name: "figure-vector-redraw"
description: "Turn a raster or AI-generated scientific concept figure into a corrected, editable vector figure at the requested dimensions on a Design canvas using the user's traced SVG pieces: audit, layout math, asset slimming, review."
---

# Scientific concept figure -> corrected vector figure on a Design canvas

Use when the user shows a conceptual figure (often AI-generated; e.g. Input -> Deep-learning model -> Output pipelines) and wants it checked, vectorized and rebuilt as an editable figure. Finishing work afterwards (style, alignment, whitespace, comments) continues in `figure-style-refine`; build so that stage is cheap (see "Build for the finishing stage").

## Working style for this user
- Reply in Korean, formal and concise: one-line outcome, details in bullets.
- Work in stages and wait for the go-ahead between them: audit -> text-only layout -> simple shapes -> user's real assets -> background/style -> alignment review. "일단 확인만" means audit only, build nothing.
- Fidelity to the original look is valued at first (background, text placement, panel titles). Keep scientific corrections anyway, and list anything you dropped so the user can restore it. Expect the user to strip decoration later (see Stage 4).
- If the user picks a notation that deviates from convention (e.g. W_i on GAT edges instead of alpha_ij), apply it and mention the convention once.
- Do not add content the original does not have (e.g. predicted tissue maps); offer it as an option instead. Added maps were removed with "이런 내용이 없어".

## Stage 1 - Scientific audit (before drawing)
Crop regions with PIL and inspect at 2x. Check:
- Duplicate or missing labels; count arrows vs reactions (AI images often draw 9 arrows for the 8 TCA steps and duplicate a label such as Succinate). Redraw as one arrow per step.
- Cluster plots: one label per cluster/colour, no unlabeled clusters. Axes and colour-bar "high/low" ticks on illustrative UMAPs/maps were removed by the user; do not add them unless asked.
- Notation: in a GAT the edge-specific values are attention coefficients alpha_ij; W is the shared weight matrix; GAT is a kind of GNN, so two side-by-side panels need a stated relationship.
- Claims vs encoding: "flux" needs stoichiometric constraints (S v = 0) or it is "pathway activity"; "spatially resolved" needs a spatial output (tissue map), not only a coloured cycle.
- Biology sanity (e.g. cortical Layer I is neuron-sparse).
- Typography: no hyphen after -ly adverbs ("spatially resolved"). Never break a word with a hyphen to fit a box ("Oligo-/dendrocyte" was rejected); move or resize instead. The user also drops optional compound hyphens ("cell type specific"); keep hyphens that are part of a name (α-Ketoglutarate, Succinyl-CoA).
- Generative-AI watermarks (corner sparkle): never reproduce; journals restrict generative images.
- Prior art via PubMed (e.g. scFEA, Genome Res 2021, https://doi.org/10.1101/gr.271205.120); cite with DOI.
Deliver a table (location / problem / fix) plus the open decisions.

## Stage 2 - Canvas and text layout
- Use the requested width and height or the dimensions required by the final destination. Otherwise reuse the existing artboard or source aspect ratio when it suits the content. Choose a layout for the figure if there is no suitable reference size. Set the dimensions in `canvas.json` when needed, and keep one artboard in the end ("Artboard 1로 통일").
- Size panels and margins for the chosen artboard. Keep the reading order, align related cards and give each panel enough room for its text and graphics. Stack panels vertically when the target width is narrow.
- In one 1920×1080 slide layout, the outer margins were 52px and the 64px gutters held the flow arrows. Input, model and output columns were 560px, 516px and 612px wide. Column headers started at y=40, cards occupied y=80–986 and the bottom figure title started at about y=1008. Align row splits across related columns when the figure uses more than one row.
- Set type sizes for the final placement and keep the text editable. In the slide example, NanumBarunGothic column headers and the figure title were 36px, card and legend titles 28px, subtitles and captions 25px, legend text 24px, ring labels 23px, plot annotations 20–22px and ring centre text 32–36px. Check legibility at the actual insertion size. Align same-level titles within each row.
- One left axis per card: title, subtitle, caption and legend start 16px inside the card, on the same x as the column header above.
- Undecided terminology -> a data-props enum tweak (e.g. outputTerm: Pathway activity / Metabolic flux) feeding holes in the titles; replace holes with literal text once decided (holes are not editable in the canvas).
- Measure text with the font actually used on the board before placing it (Liberation Sans has Arial metrics):
  ```python
  from PIL import ImageFont
  f = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 16)
  f.getlength('α-Ketoglutarate')   # ~110 px
  ```
- Every text box stays inside its card (inner padding >= 12-16) and inside the outer margins.

### Labels around a ring (TCA cycle)
- Ring centre = geometric centre of the circle (not the ink bbox; arrowheads skew it). Put the ring-centre title exactly there.
- Place labels at the junctions (head meets next tail), then set every label to the same ink-to-ink gap (16px) from the ring with `ring_label_gap.py` (figure-style-refine scripts). On a regular ring, mirrored labels share one y; top/bottom labels centre on the ring axis.
- Centre the ring+labels group optically in the card (ink extents between the title bottom and the card bottom).
- A round diagram is width-limited by its side labels; compute that limit before promising to "fill" a tall card.

### Labels on graph edges
- Edge midpoint + perpendicular offset >= half label width + 4 from the line. Check against other edges at that height, node discs and other label boxes.
- Plain text only (no background pills), W<sub>n</sub>; number all edges in a readable order; a drawn double (bidirectional) line counts as one edge unless asked. At the final 20-22px size, widen node spacing (e.g. vertical x1.15) instead of shrinking labels.

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
9. Art cut off at the image edge (e.g. half clusters at the top): do not fade it (a fade makes neighbouring elements look cut too). A mirrored patch (scaleY(-1) copy masked onto the cut element) left double borders and mismatched inner edges; the accepted fix was to redraw the cut elements as complete vectors with the same structure as their intact siblings (same node count, inner web, hub, region) and re-attach the connecting edges to the new nodes.
10. Simple glyphs the AI drew unevenly (cycle arrows, flow arrows) are better regenerated than traced: `ring_arrows.py --steps 8 --style chain` gives identical interlocking step arrows (style-refine scripts). Give the input and output cycles the same arrow grammar.

## Stage 4 - Background and cards
- Default now: one solid light background (#f3f5f8) with flat white cards (1px #d0d7de, radius 8, no shadow). The user first wanted the original circuit-board look, faded it to 0.4, and finally asked to remove it ("배경 회로 문양 지워주고, 단색으로").
- If the original look is requested, put the whole motif in ONE `<svg aria-hidden>` as the first child of the root so it can be faded or deleted in one step: radial gradient (#fff centre -> #dbe2ea edge); 1.5px traces #a3afb8 and #c5ced6 with 45-degree bends; filled pads r ~5; 2x5 square-pad grids; ghost rects #d4dbe2; barcode stripes. Only in margins and gaps between cards, clear of every text box; when card gaps move, move the gap traces with them.
- Every column needs a card or it melts into the background. Plot frames 1px #9aa4ad (not black). Flow arrows sit at the vertical centre of the cards they connect.

## Stage 5 - Review loop
Build a local preview: take the fragment between <x-dc> and </x-dc>, drop the <helmet> tags, replace /_blob/<id> with local files (keep a blob-id -> local-file map from every upload) and fill the holes. Pass the artboard dimensions with `--width` and `--height` to `render.js` or `dc_preview.py`. Use the same dimensions for `ring_label_gap.py` when adjusting ring labels. Render at 1x and 2x and crop each card for review. Check text clipping, left alignment, matching row splits and caption baselines where applicable, even ring label gaps, legend clearance, stray background pieces and label overlaps. Report findings ranked by importance and apply them once the user agrees. Send before/after or option images (2–3 strengths side by side).

## Build for the finishing stage
- Text stays live and editable: literal strings in divs, the board font loaded with @font-face, never outlined.
- Never lay a full-board overlay SVG on top: the editor selects an <svg> as one block, so it blocks every text under it. Give each leader/legend line its own small SVG, placed before the text in DOM order.
- Keep each art piece a separate element (one img/div per panel) with a clean alt/aria-label; later steps swap one asset URL at a time.
- Expect the editor to rewrite `<path/>` as `<path></path>` and to nest dragged elements inside cards (card-relative coordinates).

## Canvas etiquette
- Re-read the artboard before each publish, and diff it against your last published copy: any difference is the user's own edit (text, sizes, deletions, moves). Apply your change on top of the live file; once the user edits by hand, stop regenerating the board from scripts. If a publish result says a page-saved version was replaced, tell the user which file was overwritten and re-apply their edits.
- Respect what the user deletes or rewrites (removed annotations, case changes, hyphen removals): do not reintroduce it.
- Comment threads: the anchor `#N:1/K` points at the K-th direct child of the artboard root (0-based, background svg = 0; every tag counts). "여기/이쪽" means that element. Make the change, reply in the thread (what changed, by how much, what stayed), write one line in the session, and leave the thread unresolved unless the user asks you to resolve it.

## Helper scripts (scripts/ in this repo)
Scripts live in the GitHub repo `hpend2373/figure-vector-redraw`: `scripts/` for this skill, `style-refine/scripts/` for the finishing tools. Fetch a file when the working folder lacks it:
```bash
curl -fsSL https://raw.githubusercontent.com/hpend2373/figure-vector-redraw/main/scripts/svg_split.py -o scripts/svg_split.py
```
- `svgo.config.cjs` - svgo settings that keep mask ids and path order (Stage 3, step 4).
- `svg_split.py` - cut a traced SVG into pieces that each keep the mask: `--pieces N` before svgo, `--max-bytes 1500000` for upload chunks (Stage 3, steps 4-5).
- `svg_merge.py` - merge svgo-optimised pieces back into one file.
- `svg_remove_boxes.py` - drop icon paths by bbox, remove light halos, add black mask ellipses (Stage 3, step 6).
- `grid_revectorize.py` - spot-grid maps to run-length rect SVGs, artefact repair, illustrative derived maps (Stage 3, step 7).
- `measure_text.py`, `ring_labels.py` - text widths and first-pass label boxes around a ring (Stage 2); finish with `style-refine/scripts/ring_label_gap.py`.
- `build_preview.py` + `render.js` - standalone preview of an artboard and Chromium renders of SVGs, stacked chunks and pages (Stages 3 and 5).
- `style-refine/scripts/ring_arrows.py`, `umap_spread.py`, `dc_preview.py` - step-arrow cycles, cluster-preserving scatter spread, Python preview renderer.
