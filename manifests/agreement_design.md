# Tool agreement section — design notes (23 Sep 2026)

The backend (`src/agreement.py`, `/jobs/{id}/agreement` and
`/jobs/{id}/agreement/genes`) already existed. This session replaced the
frontend, which had shipped as a plain bar-list ("like line" — the request
that started this), with an actual Venn diagram for 2–4 tools and a
recoloured UpSet-style list for all five, plus the click-through detail box
neither had yet: genes, a column picker, export, and a button that starts an
enrichment run scoped to exactly the genes in one region.

## What changed and where

- `src/agreement.py` — `build()` now accepts 1 tool, not just 2+ (a single
  circle at 100% is a legitimate degenerate case, and the frontend's tool
  checkboxes allow it). Every region now carries `pct` (of the union, so
  regions sum to 100), `label` and `note` — computed once, server-side, by
  new `region_label()`/`describe_region()` helpers, so the figure's own
  wording and an enrichment run started from a click on it can never
  describe the same genes two different ways.
- `src/geneset.py` — `select()` gained a `genes` bypass: an explicit Entrez
  list short-circuits every tick-box rule. This is what lets "run enrichment
  on this region" reuse the existing enrichment pipeline instead of a
  parallel one.
- `src/enrichment.py` / `src/api.py` — `EnrichmentRequest` gained `genes`,
  `included`, `excluded`. When `genes` is set, `create()` overrides the
  stored `rule_sentence` with `agreement.region_label()` so the enrichment
  panel names the region the same way the diagram did. `SPEC_KEYS`/
  `normalise()` sort the gene list before hashing, so two clicks on the same
  region reuse the same cached run regardless of fetch order.
- `/jobs/{id}/agreement/genes` — ceiling raised from 1,000 to 20,000 (the
  page size for the on-screen table stayed the same; the export button and
  the enrichment button both need the *whole* region in one call, and
  19,363 MANE Select genes is the largest a region could ever be).
- `scripts/build_page.py` — `AGREE_CSS`/`AGREE_JS` rewritten. The bar-list
  renderer is kept, recoloured, for the five-tool UpSet case; a new
  `agRenderVenn()` draws real overlapping circles/ellipses for 1–4 tools.

## The Venn shapes are measured, not drawn by eye

Circle/ellipse positions for 2 and 3 sets are the standard symmetric
layouts. Four sets cannot be four circles (no arrangement of circles gives
all 15 regions — this is a known result), so it needs ellipses, and a
naive symmetric placement leaves some of the 15 regions with zero area.
Rather than copy published coordinates from memory and hope, the layout was
found the way the rest of this codebase finds things: a dense grid
(3 px pitch) was tested against candidate ellipse placements, points
bucketed by which ellipses contain them, and the placement kept was the one
whose *smallest* region still held the most grid points, inside sane bounds
(rx 200–300, ry 90–150, so the shapes stay ellipse-shaped rather than
degenerating into something huge). Kept parameters (four congruent
ellipses, `rx≈277, ry≈110`, tilted `±45°`/`±51°`, centres 20 px and 110 px
either side of a shared midline): all 15 regions non-empty, smallest region
≈1% of the figure's area — small but real, and every region's own
percentage chip sits at that region's sampled centroid, not a guessed
point, so a chip is never accidentally rendered in the wrong bucket.
The same grid-centroid technique gave the 1-, 2- and 3-set label positions
too, so all four layouts came from one method rather than three different
ones.

Region identity is bitmask-over-shape-letter (A/B/C/D), assigned to
whichever tools are ticked in a fixed order (`CANON`, matching the
registry) at render time — never a fixed tool→letter mapping, since any 2–4
of the five tools can be the ones on screen.

## Colour: validated, not eyeballed

Five tools need five fixed hues (dataviz skill: categorical, fixed order,
never cycled). Run through `scripts/validate_palette.js --pairs all` (the
Venn's overlapping fills are the "any two marks can be neighbours" case,
not the adjacent-only one bar charts get) in both light and dark, against
every 4-, 5- and 8-hue subset of the documented 8-hue palette: **no 5-hue
subset of this palette clears every check in both modes** — the closest
achievable is one hard fail (dark-mode aqua vs. green, ΔE 11.9, just under
the 15 floor). That is a property of asking eight hard-gated hues to also
survive blended translucent overlap five-wide, not a bug in the search.

Kept: seed = blue `#2a78d6`/`#3987e5`, TargetScan = aqua `#1baf7a`/`#199e70`,
RNAhybrid = yellow `#eda100`/`#c98500`, miRTarBase = red `#e34948`/`#e66767`,
scanMiR = green `#008300` (mode-invariant). This is why identity in the
figure is never colour-alone: every circle also has a fixed position in the
standard layout, and the tools checkbox row (`#agtools`) doubles as the
legend — a swatch beside a name the reader already reads, not a second
legend nobody reads. miRTarBase (`kind: "evidence"`, not `"prediction"`)
gets a diagonal hatch on top of its own fill as well, the dataviz skill's
texture channel — one more cue that survives greyscale/print and doesn't
spend a second hue.

Blend mode is theme-aware: `multiply` in light mode gives classic
Venny-style colour mixing; `multiply` against a dark surface only goes
black, so dark mode uses `screen` instead, which lightens on overlap.

## What the click gives you

Clicking a chip (Venn) or a row (UpSet) opens `#agdetail` below the figure:
the region's own label and a one-sentence note (`describe_region()` —
mixed evidence+prediction, pure prediction, or evidence-only, worded
differently), a paginated gene table with a column picker (which of the
region's *own* tools to show — the excluded ones have nothing to show by
definition), a CSV export, and "Run enrichment on these genes". The last one
POSTs the region's Entrez list to the existing `/jobs/{id}/enrichment`
endpoint and hands the run straight to `watchRun()` — the same function the
tick-box flow uses — so the result renders in the existing Pathway Analysis
panel with no second rendering path to keep in sync. The full gene list for
export/enrichment is fetched lazily, only on the click that needs it, not
eagerly when the region is opened — most regions someone looks at are never
exported or sent to enrichment, and eagerly pulling up to 20,000 rows for
each one would be pure waste.

Filters travel with the figure: `agFilterQS()` reads the same region
checkboxes, 6mer toggle and gene search the results table already applies
(`exportRegions()`/`show6`/`PAGE.q`) and sends them on the `/agreement` and
`/agreement/genes` calls — matching this section's own stated promise
("computed over exactly the rows the table is showing"), which the
previous bar-list version did not actually keep (it sent `tools=` only).

## Verification

- `src/agreement.py`, `src/geneset.py`, `src/enrichment.py`: exercised
  against a real in-memory SQLite database built from `schema.sql` — a
  3-tool overlap example (regions sum to exactly 100.0%), the new 1-tool
  case, `region_genes()`'s inclusion/exclusion logic, and
  `enrichment.create()`'s sentence override and cache-hit behaviour
  (`find()` reuses a run regardless of gene-list order).
- `src/api.py`: `EnrichmentRequest`/`_spec()` exercised directly against
  the pinned `pydantic`/`fastapi` versions for both request shapes (tick
  boxes; explicit gene list).
- `scripts/build_page.py`: regenerated `web/index.html` from the untouched
  `web/layout-source.html` with no assertion failures; the emitted
  `<script>` passes `node --check`; brace count in the emitted `<style>`
  balances.
- The four Venn layouts (1–4 tools) and the five-tool UpSet list were each
  rendered standalone (Playwright, the extracted CSS/JS from the real
  build) in light and dark mode — every region's chip lands inside its own
  region, text is legible on every fill, no console errors.

## Open

- The single hard CVD fail (dark-mode aqua/green) means a colour-blind
  reader in dark mode could, in principle, confuse those two circles'
  *pure* fill in a region where only one of them is present — position and
  the legend are what actually carry identity there, by design, but it is
  worth a real user check rather than taking the search's word for it.
- Region colouring assumes at most 4 simultaneous fills; that is exactly
  `VENN_MAX_SETS`, so it cannot drift out of sync with the Venn/UpSet
  cutoff by construction — but if that constant ever changes, the palette
  search needs re-running, not just the cutoff.

## Revision: capped at 4, every region shown, self-labelling (23 Sep, later same day)

Two things changed after the diagram above was already live: the user
sent a screenshot of it with all five tools ticked (correctly falling back
to the list, by design) alongside a Venny reference image, and asked for a
real Venn there too rather than the list; separately, only the regions a
gene actually landed in were being drawn, which for a small gene set looked
like the figure was missing slices rather than reporting them at zero.

**The tool picker now caps at 4, instead of the diagram falling back to a
list at 5.** `agToolBoxes()` disables whatever is left unticked once four
boxes are checked (`agSyncToolCap()`), with a line of text under the row
saying so while it's in effect. A job that ran five tools defaults to the
first four in `CANON` order rather than all five — `agreeRender()` checks
this before the first paint and silently re-fetches with `tools=` set,
so a 5-tool job never flashes the list before the cap has a chance to
apply. The five-tool list renderer (`agRenderUpset`) is untouched and
still exists — nothing in the UI can reach it now, but the backend's
`display: "upset"` path stays as a fallback if `/agreement` is ever called
directly with 5 tools (`scripts/build_page.py`, not `src/agreement.py`,
is what enforces the cap; the API itself still answers a 5-tool request).

**Every combination gets a region now, not just the ones with a gene in
them.** `agreement.py`'s `build()` used to filter `regions.items()` down to
non-empty combinations before turning them into API rows; it now builds
the full `2**n - 1` combinations with `itertools.combinations` first and
looks up each one's count (`regions.get(k, 0)`), so an empty combination
still gets a `0%` region rather than not existing. Percentages still sum
to exactly 100 — the empty ones just contribute nothing. This is also
closer to what "Venny" itself does, which was the reference the user sent.

**Each region is now a small card, not a bare number**, and each circle is
labelled with its own tool's name:

- The percentage chip is a rounded card (`.agchip rect`, replacing the
  plain circle) carrying two lines — the percentage and, smaller and
  dimmer, the raw count in parens — plus a row of small dots underneath,
  one per tool actually in that region, in that tool's own fixed hue. This
  is the same dot-per-tool device the five-tool list already used
  (`.agdot`), now inside the Venn too, so a region's exact membership never
  depends on tracing which overlapping shapes it happens to sit inside.
  Card size steps down with `n` (`CHIP` in `AGREE_JS`) since the 4-set
  layout's smallest regions are ~1% of the figure's area — a card sized for
  the single-circle case would swallow them.
- Each circle's own name is printed just outside its own boundary
  (`agSetLabelAnchor()`, `.agsetlabel`), in the tool's own colour, with a
  surface-coloured stroke underneath the fill (`paint-order`) as a halo so
  it stays legible over whatever's behind it in either theme without
  per-case contrast tuning. For a circle this is straight out from the
  cluster's centre; the 4-ellipse layout needed a different rule — two of
  its four ellipses sit on the *same side* of the shared centre (see the
  `rot` values above), so "straight out from centre" put two labels on
  top of each other. Walking out along each ellipse's own major axis
  instead separates them, because no two of the four ellipses share a
  tilt.
- The figure itself is bigger (`.agvenn` max-width 480px → 640px) now that
  each region carries more to read, and every `VENN_LAYOUT` viewBox grew a
  40-unit margin on all sides (the shape and centroid coordinates
  themselves are untouched) so the outward-pushed labels have somewhere
  to sit without needing per-layout tuning.
- The click-through gene table now says so in words when a region really
  is empty ("No gene matched this exact combination under the current
  filters") instead of rendering a table with a header and no rows.

**Verification.** `src/agreement.py` re-exercised against a fresh
in-memory SQLite fixture: a 3-tool case now returns all 7 combinations
(previously would have returned only the non-empty ones), percentages
still sum to exactly 100.0, the 5 empty combinations all carry `pct: 0.0`,
`region_genes()` returns an empty list rather than erroring for one of
them, and the 1-tool case is unaffected. `scripts/build_page.py` was
regenerated with no assertion failures; the emitted `<script>` passes
`node --check` and the `<style>` brace count balances. All four Venn
layouts (1–4 tools, including deliberately-empty regions) and the
5-tool-job-defaults-to-4 case were rendered standalone via Playwright
against the real generated page (network requests intercepted with
synthetic `/agreement` responses) in light and dark mode: every chip
lands inside its own region with no overlap, tool-name labels no longer
collide on the 4-ellipse layout, the cap note and disabled 5th checkbox
both render, and unticking back below 4 re-enables it.

## Revision: exports, default pick, real label fix, persistence, gene focus (23 Sep, third pass)

The user sent two screenshots of the 4-set diagram: "Seed analyser" and
"RNAhybrid" printed on top of a filled shape rather than beside it,
unreadable, plus a five-item list of everything else still wrong. Six
things changed.

**Region and results exports are tab-separated, not comma.** Both the
client-side region export (`agExportCSV()`, despite the old name — it now
writes `.tsv`) and the results-table export menu were affected: the latter
wasn't broken, just mislabelled and ordered so the plain-text option looked
primary. `agdetexport`'s button now reads "Export table (TSV)"; the
`ex.innerHTML` export menu puts Excel first as `expprimary` (accent-filled)
with TSV secondary, and a one-line hint explains why TSV looks sparse for a
multi-tool job (one row per stored record, not one row per gene) rather
than leaving the user to discover that by opening it. The enrichment-terms
buttons got the same reorder (`enrexpx`/`enrexp` swapped, Excel first).
Nothing server-side changed — `xlsx_export.py` already produced a properly
structured workbook; the fix was making the client point at it first.

**Tool-agreement Venn now defaults to miRTarBase + RNAhybrid + scanMiR**,
not "however many tools the job happened to run, up to the cap-of-4 from
the last revision." A new `DEFAULT_PICK` constant is tried first in
`agreeRender()`; if the job doesn't have all three, it falls back to the
existing `CANON`-order-first-4 behaviour from the previous revision. Same
one-time-refetch guard as before (`agreeRender()` returns after setting
`AGREE.picked` and calling `agreeLoad()` once, so a job doesn't flash all
its tools before settling on the default three).

**The masked-label bug was a real SVG paint-order bug, not a layout-anchor
bug.** `agRenderVenn()` used to append each shape immediately followed by
its own label, one set at a time — so set D's shape, appended fourth,
painted over set A's label, appended first, whenever their regions
overlapped. `agSetLabelAnchor()`'s positions were already correct; nothing
was actually mis-anchored, it was just underneath later paint. Fixed by
splitting into two passes over the same `LETTERS` loop: every shape (and
miRTarBase's hatch overlay) appended first, then every label appended
after, so labels are always the top layer regardless of set order. Sizes
also went up a step (`.agvenn` max-width 640px → 760px, `.agsetlabel`
13px/700 weight → 14.5px, halo stroke 5px → 5.5px) since "clear and
prominent," not just "not hidden," was the ask.

**Region-detail persistence: `loadPage()` was silently closing
`#agdetail` on every unrelated page-of-results reload.** It called
`agreeLoad()` unconditionally at the end, and `agreeLoad()` re-rendered the
whole agreement section from scratch every time, which reset
`AGREE.detail` along with everything else — so clicking a table row (which
calls `loadPage()`) closed whatever Venn region the user had just opened,
even though nothing about the agreement view had changed. Fixed by giving
`agreeLoad()` a memo key (`JOBID` + the same filter/tools query string it
already sends) and skipping the fetch/re-render entirely when the key
matches the last successful load. The detail box, being DOM state
`agreeRender()` never touches unless the *agreement* data itself changed,
now survives exactly what it should: table paging, sorting, and gene
clicks. It still closes correctly when the user changes a filter that
actually changes what the Venn shows.

**Clicking a table row now scrolls to the results table, not the binding
map.** Both live inside `#results`, with the binding-map panel positioned
above the actual table in the DOM — so `el("results").scrollIntoView()`
was scrolling to the top of that wrapper, i.e. the map, not the table the
click was supposed to reveal. `focusGene()` now targets
`#results .tablewrap` specifically and waits on `loadPage()`'s promise
before scrolling, instead of scrolling immediately against not-yet-updated
layout. (The network panel's own "show this gene's binding sites →" link
was left as-is — that one's destination genuinely is the map.)

**A "Showing GENE only" banner sits above the results table whenever a
gene filter is active**, addressing the same underlying complaint as the
scroll fix: the user could click through to a filtered table and not
register that a filter was applied at all. `wire()` inserts a
`#genebanner` div just above `.tablewrap` (once, if not already present);
`pager()` shows or hides it in lockstep with the existing "← all genes"
control and fills in the gene symbol. Styled as an accent-tinted banner
(new `--accent-wash` custom property) rather than plain text, per "big
font" in the request, with its own "show all genes" link so clearing the
filter doesn't require scrolling back up to the search box.

**A pre-existing device/repo drift was found and fixed while starting this
pass.** `src/agreement.py` and `scripts/build_page.py` on the user's
machine had reverted to their state from *before* the "capped at 4, every
region shown" revision above — missing the `all_keys` fix in particular,
so empty regions had silently stopped being shown again. Root cause wasn't
chased down; the practical fix was re-synced from the container's own
known-good mirror before layering this pass's six changes on top, and
every file this pass touches is being re-pushed in full rather than as an
incremental diff, specifically to close that gap.

**Verification.** All four Venn layouts (1–4 tools) rendered standalone
via Playwright against the real generated page, including the exact
4-tool combination (seed, RNAhybrid, miRTarBase, scanMiR) from the user's
bug screenshots, in both light and dark mode: all four tool-name labels
render as the topmost layer, fully legible with their halo, in the
position the previous revision's anchor logic already computed correctly.
The 3-tool default pick was exercised for both a job that ran exactly
those three tools and one that ran all five (falls back to `CANON`
first-4). The persistence fix was exercised by opening a region detail,
triggering an unrelated `loadPage()` (table sort), and confirming
`AGREE.detail` and `#agdetail`'s visibility survive; then changing the
filter and confirming it still closes when it should. The gene-focus
banner was exercised directly against `pager()` with `PAGE.gene` set:
`#genebanner` becomes visible and is filled with the correct symbol. The
`focusGene()` scroll-target change was verified by code/DOM-structure
review (`#results .tablewrap` sits below the binding-map panel in both
`layout-source.html` and the generated page) rather than a full simulated
click-through, since reproducing `render()`'s complete data shape in the
test harness was disproportionate to what was actually in question. The
TSV export change was verified by triggering `agExportCSV()` and checking
the produced blob is tab-separated with correctly escaped embedded
tabs/newlines. `scripts/build_page.py` was regenerated with no assertion
failures; the emitted `<script>` passes `node --check` and the `<style>`
brace count balances.

## Revision: labels actually in the margin, 0% chips gone, binding-map round-trip (23 Sep, fourth pass)

Two screenshots of the 4-set Venn again, plus three more items: the
"clear and prominent" label fix from the third pass had moved the labels
outside their OWN circle's fill, but not outside a *neighbouring* circle's
- "Seed analyser" and "RNAhybrid" were still sitting on the orange/blue
overlap, just not underneath anything anymore. Separately, the 0%
region chips (added two passes ago specifically so a figure never looked
like it was missing a slice) were now the complaint: with all combinations
shown, a 4-tool Venn draws up to 15 chips, most reading "0% (0)", and that
reads as noise, not completeness. And a new, unrelated request: clicking a
position on the binding map should jump to that record's row in the
results table below - the reverse of the click that already existed the
other way.

**Labels now clear every shape's fill, not just their own.** The previous
pass's `agSetLabelAnchor()` walked a label out from its own circle's edge
by a fixed offset along one direction; that guarantees clearing the shape
it names, but nothing else. Replaced with `agPlaceLabel()`, a small 2D
search: starting at the shape's own edge along its natural outward
direction (straight out from the cluster centre for a circle; each
ellipse's own major axis for the 4-set layout, as before), it tries a
handful of small angular detours at each distance - nearest first - until
it finds a point whose entire label *box*, not just its anchor point,
sits outside every shape's fill. "Whole box, not anchor point" mattered in
practice: the default 3-circle view packs its circles so tightly that each
pair's centre sits inside the other's radius, and a point 9px off one
circle's edge can still be deep inside a second circle once ~110px of
text hanging off that anchor is accounted for - an anchor-only check
passed while the rendered text visibly crossed a circle boundary.

**Getting the label's real box right took two more corrections.** First,
two labels that both had to retreat from a shape can still collide with
*each other* - the two same-side ellipses in the 4-set layout have own-axis
directions only ~6° apart, and a naive "if still colliding, walk further
out" response just chased both labels toward the same point and, in one
intermediate version of this fix, off the edge of the figure entirely
(screenshotted, caught, and is why the final version searches nearby
angles before ever increasing distance, and checks against every
already-placed label's box, not only the shapes). Second, the SVG `y`
attribute is the text's baseline, not its centre; the font's real box
extends 13.4px above that line and only 3.1px below (measured once via
`getBBox()` against the live render, not eyeballed), and an initial
version that treated the box as symmetric around `y` under-covered the
taller top half by enough to let a real collision through undetected in
testing. Both the shape-clearance and the label-vs-label checks, and the
new viewBox-edge check added alongside them (a label detouring around a
crowded neighbour could walk past the figure's own frame), all use these
same measured, asymmetric offsets now.

**0% region chips are no longer drawn**, in the Venn or the five-tool
UpSet list - `r.n === 0` regions are skipped entirely rather than shown as
an empty card. This directly reverses the "every combination gets a chip"
change from two passes ago; that change is still correct at the data
layer (`agreement.py`'s `build()` still returns every combination, still
sums to 100%, and still lets `region_genes()` answer a query for an empty
region cleanly) - only the frontend's decision to draw a chip for a
zero-count region changed. The shape itself is untouched: an empty
region's coloured area is still exactly where and what colour it should
be, still clickable-adjacent in the sense that its neighbours are, just
without a "0% (0)" card sitting on it. The one edge case this reopens -
every region in view being empty, which would otherwise render a diagram
with coloured shapes but no numbers on it at all, the exact "looks broken"
complaint the all-regions change was originally meant to fix - is handled
explicitly: both `agRenderVenn()` and `agRenderUpset()` now check whether
*any* region has a nonzero count and show the existing "No gene was found
by any of the selected tools under these filters" message instead when
none do.

**Clicking a position on the binding map now scrolls to its row in the
results table.** The existing click handler on a map tick/bar already
toggled `selSite` and re-rendered; it now also calls a new
`flashTableSite(k)`, the mirror of the existing `flashSite(k)` (table row
→ map). Finding the right target took establishing the actual DOM
relationship first: `detailRow()`/`rawSites()` render a per-gene site
table (`.sites`, with one `<tr data-k="...">` per stored record) as an
expanded row *inside the main results table itself*, immediately under
the clicked gene's own row - a different element from `#map`, the
binding-map panel, which sits in its own place above the whole table (see
the previous pass's note on that DOM layout). So "the result table" the
request asked for is `#results .sites [data-k="..."]`, and the existing
`sitesel` CSS class (a persistent background wash, not the map's
transient `.flash` animation) already highlights it correctly once
`render()` redraws the row selected - the fix only needed to bring that
row into view, not draw a new highlight for it.

**Verification.** All four Venn layouts (1-4 tools, including the job's
own default 3-tool view and the exact 4-tool combination from the user's
screenshots) rendered standalone via Playwright: every label's real
`getBBox()`, sampled at its corners and edge midpoints, tested clear of
every shape and every other label (an ellipse point-membership test doing
the checking, the same rotation math the frontend itself uses) and inside
the SVG's own viewBox, in both themes; every chip's percentage text
confirmed to contain no "0%" entry; a synthetic all-zero case confirmed to
fall back to the "no gene found" message instead of a numberless diagram.
The binding-map round-trip was exercised through the real click handlers
end to end, not in isolation: `loadPage()`'s full `applyData()`/`render()`
pipeline (previously assumed too heavy to mock, per the prior pass's
notes - it turned out the harness's mock miRTarBase status string just
didn't match a real `MTC` key, not that the pipeline itself was
unreachable), a real click on the map's first site button, and a captured
`Element.prototype.scrollIntoView` call confirmed to land on the matching
`data-k` row inside `#results .sites`; a second click (deselecting)
confirmed *not* to fire a second scroll; and the reverse direction
(table row → map, unrelated to this pass's change) re-confirmed still
flashes the correct tick. `scripts/build_page.py` was regenerated with no
assertion failures; the emitted `<script>` passes `node --check` and the
`<style>` brace count balances. All four changed-file writes to the user's
machine were re-verified byte-for-byte against a fresh read after
writing, per the previous pass's note that the write path itself
occasionally lands stale content despite reporting success - it did so
again this round (`build_page.py` and `index.html` both needed one retry
each), confirming that note is still the right practice, not a one-off.
