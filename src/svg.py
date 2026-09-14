"""Static pictures for the HTML report, drawn as inline SVG.

Why SVG and not the interactive versions: the report's whole value is being
one self-contained file. The moment it needs vis-network from the server it
only works while that server is running and is broken as an email
attachment. SVG is a list of drawing instructions that lives inside the
document, prints at print resolution rather than screen resolution, and
needs no JavaScript at all.

Why the layout is computed here rather than by physics in a browser: a
report is a dated document that may be cited, so the same job must give the
same picture every time. The layout below is fully deterministic - the
starting positions are fixed by node order, not randomised - so re-rendering
a report cannot quietly rearrange a figure someone has already referred to.

What is lost: dragging, hover, zoom. That is the honest trade, and the
interactive versions stay on the page.
"""
import html
import math

# ---------------------------------------------------------------- helpers


def _esc(v):
    return html.escape("" if v is None else str(v))


def _n(x):
    """Coordinates at one decimal: enough for a drawing, half the bytes."""
    return ("%.1f" % x).rstrip("0").rstrip(".")


# ------------------------------------------------------------- the network

# The layout is O(n^2) per iteration in plain Python. Sixty nodes is already
# a busy figure on a printed page, and past that the labels collide into
# nonsense, so the report draws the strongest N and says how many it left out
# rather than producing an unreadable hairball slowly.
MAX_NODES = 60
ITERATIONS = 260


def _layout(node_ids, edges, centre_id, width, height):
    """Force-directed layout: linked nodes attract, all nodes repel.

    Fruchterman-Reingold, with two deliberate departures. Starting positions
    come from node order rather than a random seed, so the result is
    reproducible; and the miRNA is pinned at the centre, because it is
    connected to everything and would otherwise be pushed to an edge by its
    own attraction to all sides at once.
    """
    n = len(node_ids)
    if n == 0:
        return {}
    cx, cy = width / 2.0, height / 2.0
    pos = {}
    others = [i for i in node_ids if i != centre_id]
    r0 = 0.36 * min(width, height)
    for j, i in enumerate(others):
        a = 2 * math.pi * j / max(1, len(others))
        pos[i] = [cx + r0 * math.cos(a), cy + r0 * math.sin(a)]
    if centre_id in node_ids:
        pos[centre_id] = [cx, cy]

    k = 0.85 * math.sqrt((width * height) / float(n))
    adj = [(e["from"], e["to"], 1.0 if e["kind"] == "target" else 0.45)
           for e in edges if e["from"] in pos and e["to"] in pos]
    temp = width / 8.0

    for step in range(ITERATIONS):
        disp = {i: [0.0, 0.0] for i in pos}
        ids = list(pos)
        for a in range(len(ids)):
            ia = ids[a]
            for b in range(a + 1, len(ids)):
                ib = ids[b]
                dx = pos[ia][0] - pos[ib][0]
                dy = pos[ia][1] - pos[ib][1]
                d2 = dx * dx + dy * dy
                if d2 < 0.01:
                    # identical positions have no direction to push apart in,
                    # so nudge them deterministically by index instead
                    dx, dy, d2 = (a - b) * 0.1 + 0.05, (b - a) * 0.1, 0.01
                d = math.sqrt(d2)
                f = (k * k) / d
                disp[ia][0] += dx / d * f
                disp[ia][1] += dy / d * f
                disp[ib][0] -= dx / d * f
                disp[ib][1] -= dy / d * f
        for u, v, w in adj:
            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            d = math.sqrt(dx * dx + dy * dy) or 0.01
            f = (d * d) / k * w
            disp[u][0] -= dx / d * f
            disp[u][1] -= dy / d * f
            disp[v][0] += dx / d * f
            disp[v][1] += dy / d * f
        t = temp * (1.0 - step / float(ITERATIONS)) + 0.5
        for i in pos:
            if i == centre_id:
                continue
            dx, dy = disp[i]
            d = math.sqrt(dx * dx + dy * dy) or 1.0
            pos[i][0] += dx / d * min(d, t)
            pos[i][1] += dy / d * min(d, t)
    return pos


def _fit(pos, width, height, pad):
    """Scale the settled layout into the viewport, keeping proportions."""
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    if not xs:
        return pos
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx = (width - 2 * pad) / (x1 - x0) if x1 > x0 else 1.0
    sy = (height - 2 * pad) / (y1 - y0) if y1 > y0 else 1.0
    s = min(sx, sy)
    ox = pad + ((width - 2 * pad) - (x1 - x0) * s) / 2.0
    oy = pad + ((height - 2 * pad) - (y1 - y0) * s) / 2.0
    return {i: (ox + (p[0] - x0) * s, oy + (p[1] - y0) * s)
            for i, p in pos.items()}


def network(data, width=860, height=560):
    """The target network as one inline SVG. `data` is network.build()."""
    nodes = list(data["nodes"])
    centre = None
    for n in nodes:
        if n["group"] == "mirna":
            centre = n["id"]
    genes = [n for n in nodes if n["id"] != centre]

    dropped = 0
    if len(genes) > MAX_NODES:
        # keep the best-supported genes: a figure of the strongest targets is
        # a figure, a figure of six hundred is an ink blot
        genes = sorted(genes, key=lambda g: (-g["n_tools"], g["id"]))[:MAX_NODES]
        dropped = len(data["nodes"]) - 1 - len(genes)
    keep = {g["id"] for g in genes} | ({centre} if centre else set())
    edges = [e for e in data["edges"]
             if e["from"] in keep and e["to"] in keep]

    ids = ([centre] if centre else []) + [g["id"] for g in genes]
    pos = _fit(_layout(ids, edges, centre, width, height), width, height, 46)

    out = ['<svg class="netsvg" viewBox="0 0 %d %d" width="100%%" '
           'xmlns="http://www.w3.org/2000/svg" role="img" '
           'aria-label="miRNA target network">' % (width, height)]

    # shared-term links first so they sit behind the target links
    for e in edges:
        if e["kind"] != "shared_terms":
            continue
        a, b = pos.get(e["from"]), pos.get(e["to"])
        if not a or not b:
            continue
        w = min(3.2, 0.7 + 0.45 * e["value"])
        out.append('<line class="ed-share" x1="%s" y1="%s" x2="%s" y2="%s" '
                   'stroke-width="%s"/>'
                   % (_n(a[0]), _n(a[1]), _n(b[0]), _n(b[1]), _n(w)))
    for e in edges:
        if e["kind"] != "target":
            continue
        a, b = pos.get(e["from"]), pos.get(e["to"])
        if not a or not b:
            continue
        out.append('<line class="ed-target" x1="%s" y1="%s" x2="%s" y2="%s" '
                   'stroke-width="%s"/>'
                   % (_n(a[0]), _n(a[1]), _n(b[0]), _n(b[1]),
                      _n(0.8 + 0.85 * e["value"])))

    for g in genes:
        x, y = pos[g["id"]]
        r = 6.5 + 2.4 * g["n_tools"]
        cls = "nd-val" if g["group"] == "validated" else "nd-pred"
        out.append('<circle class="%s" cx="%s" cy="%s" r="%s"/>'
                   % (cls, _n(x), _n(y), _n(r)))
        # the white stroke under the text keeps a label readable where it
        # crosses a link, without hiding the link behind a box
        out.append('<text class="nd-lab" x="%s" y="%s">%s</text>'
                   % (_n(x), _n(y + r + 12), _esc(g["label"])))

    if centre and centre in pos:
        x, y = pos[centre]
        s = 15.0
        out.append('<polygon class="nd-mir" points="%s,%s %s,%s %s,%s %s,%s"/>'
                   % (_n(x), _n(y - s), _n(x + s), _n(y),
                      _n(x), _n(y + s), _n(x - s), _n(y)))
        out.append('<text class="nd-lab nd-mirlab" x="%s" y="%s">%s</text>'
                   % (_n(x), _n(y + s + 14), _esc(data["mirna"]["name"])))

    out.append("</svg>")
    return "".join(out), dropped


# --------------------------------------------------------- the binding map

REGION_FILL = {"5UTR": "reg5", "CDS": "regc", "3UTR": "reg3"}
REGION_LABEL = {"5UTR": "5′UTR", "CDS": "CDS", "3UTR": "3′UTR"}

# Ranked best first, the seed analyser's own published order.
SITE_RANK = ["8mer", "7mer-m8", "7mer-A1", "6mer"]


def _ticks(length):
    """Major tick spacing that keeps roughly five to ten labels on the axis."""
    if length > 6000:
        return 2000
    if length > 3000:
        return 1000
    if length > 1200:
        return 400
    return 200


def _tick_label(p, length):
    if p == 0:
        return "0"
    if length > 2000:
        s = ("%.1f" % (p / 1000.0)).replace(".0", "")
        return s + "k"
    return str(p)


def binding_map(symbol, refseq, length, regions, seed_sites, rh_sites,
                width=820):
    """One transcript drawn to scale, with its sites.

    Exactly one transcript per picture - the MANE Select one that was
    scanned - because a position only means anything against the sequence it
    was measured on. Two lanes, kept apart on purpose: the seed analyser
    reports a category at a point, RNAhybrid reports an energy over a span,
    and drawing them on one line would imply they are the same measurement.
    """
    L = max(1, int(length or 1))
    left, right = 56, 18
    plot = width - left - right
    # the ruler sits below the title rather than beside it: a tick label near
    # the left edge would otherwise land on top of the gene name
    y_ruler, y_bar, y_seed, y_rh = 38, 58, 106, 154
    height = 200

    def X(p):
        return left + (max(0, min(L, p)) / float(L)) * plot

    o = ['<svg class="mapsvg" viewBox="0 0 %d %d" width="100%%" '
         'xmlns="http://www.w3.org/2000/svg" role="img" '
         'aria-label="Binding sites on %s">' % (width, height, _esc(symbol))]

    o.append('<text class="mp-title" x="0" y="12">%s <tspan class="mp-tx">%s '
             '· %s nt</tspan></text>'
             % (_esc(symbol), _esc(refseq), "{:,}".format(L)))

    maj = _ticks(L)
    minor = maj / 4.0
    p = 0.0
    while p <= L:
        x = X(p)
        is_major = abs(p / maj - round(p / maj)) < 1e-9
        o.append('<line class="mp-tick%s" x1="%s" y1="%s" x2="%s" y2="%s"/>'
                 % (" mp-maj" if is_major else "", _n(x),
                    y_ruler - (7 if is_major else 4), _n(x), y_ruler))
        if is_major:
            o.append('<text class="mp-tlab" x="%s" y="%s">%s</text>'
                     % (_n(x), y_ruler - 10, _tick_label(int(p), L)))
        p += minor

    for name, a, b in sorted(regions, key=lambda r: r[1]):
        x0, x1 = X(a), X(b)
        w = max(1.0, x1 - x0)
        o.append('<rect class="%s" x="%s" y="%s" width="%s" height="16" '
                 'rx="2"/>' % (REGION_FILL.get(name, "regc"), _n(x0),
                               y_bar, _n(w)))
        if w > 34:
            o.append('<text class="mp-reg" x="%s" y="%s">%s</text>'
                     % (_n(x0 + w / 2.0), y_bar + 12,
                        _esc(REGION_LABEL.get(name, name))))

    o.append('<text class="mp-lane" x="0" y="%s">seed</text>' % (y_seed - 12))
    if seed_sites:
        # labels alternate above and below the lane so neighbouring sites do
        # not overwrite each other on a crowded transcript
        for i, s in enumerate(sorted(seed_sites, key=lambda s: s["pos_start"])):
            x = X((s["pos_start"] + s["pos_end"]) / 2.0)
            rank = (SITE_RANK.index(s["site_type"])
                    if s["site_type"] in SITE_RANK else 3)
            h = 15 - 2.5 * rank
            o.append('<line class="mp-seed s%d" x1="%s" y1="%s" x2="%s" '
                     'y2="%s"/>' % (rank, _n(x), y_seed - h, _n(x), y_seed))
            o.append('<text class="mp-slab" x="%s" y="%s">%s</text>'
                     % (_n(x), y_seed + (13 if i % 2 == 0 else 24),
                        _esc(s["site_type"])))
    else:
        o.append('<text class="mp-none" x="%s" y="%s">no seed site on this '
                 'transcript</text>' % (left, y_seed))

    o.append('<text class="mp-lane" x="0" y="%s">RNAhybrid</text>'
             % (y_rh - 12))
    if rh_sites:
        for i, r in enumerate(sorted(rh_sites, key=lambda r: r["pos_start"])):
            x0, x1 = X(r["pos_start"]), X(r["pos_end"])
            # A 22 nt duplex on a 6,800 nt transcript is a quarter of a pixel
            # wide. Drawn true to scale it vanishes, so a duplex is never
            # narrower than this - the bar marks where it is, and the span is
            # still exact in the table and the TSV.
            w = max(7.0, x1 - x0)
            strong = (r["score"] or 0) <= -22
            o.append('<rect class="mp-dup%s" x="%s" y="%s" width="%s" '
                     'height="10" rx="2"/>'
                     % (" strong" if strong else "", _n(x0), y_rh - 10, _n(w)))
            if r["score"] is not None:
                o.append('<text class="mp-slab" x="%s" y="%s">%.1f</text>'
                         % (_n(x0 + w / 2.0),
                            y_rh + (13 if i % 2 == 0 else 24), r["score"]))
    else:
        o.append('<text class="mp-none" x="%s" y="%s">no duplex below the '
                 'cutoff</text>' % (left, y_rh))

    o.append("</svg>")
    return "".join(o)


# CSS for both pictures. Kept here beside the drawing code so a change to a
# shape and a change to its colour are never in two different files.
CSS = """
.netsvg, .mapsvg{display:block;width:100%;height:auto}
.netsvg{margin:4px 0 2px}
.ed-target{stroke:#78838f;stroke-linecap:round}
.ed-share{stroke:#aab5c0;stroke-dasharray:2 4;stroke-linecap:round}
/* teal against amber: a strong contrast that also survives red-green colour
   blindness, where the earlier pale green and pale blue did not. The miRNA
   keeps a diamond as well as its own colour, so it never relies on hue. */
.nd-val{fill:#0d7d74;stroke:#0a5d56;stroke-width:1.6}
.nd-pred{fill:#f6dfba;stroke:#d4881a;stroke-width:1.8}
.nd-mir{fill:#12314f;stroke:#15181d;stroke-width:1.2}
.nd-lab{font-size:12.5px;text-anchor:middle;fill:#15181d;
  paint-order:stroke;stroke:#fff;stroke-width:3.5px;stroke-linejoin:round}
.nd-mirlab{font-size:14px;font-weight:700}
.netkey-svg{display:flex;flex-wrap:wrap;gap:6px 20px;margin:6px 0 0;
  font-size:12.5px;color:#5c6670}
.netkey-svg b{display:inline-block;width:10px;height:10px;border-radius:50%;
  margin-right:5px;vertical-align:-1px}

.mp-title{font-size:12.5px;font-weight:600;fill:#15181d}
.mp-tx{font-weight:400;fill:#8a929c;font-size:11px}
.mp-tick{stroke:#c9d0d8;stroke-width:1}
.mp-tick.mp-maj{stroke:#9aa4ae}
.mp-tlab{font-size:9.5px;text-anchor:middle;fill:#8a929c}
.reg5{fill:#dfe7ee}.regc{fill:#c3d3e0}.reg3{fill:#e9eef3}
.mp-reg{font-size:9.5px;text-anchor:middle;fill:#3d4a57;font-weight:600}
.mp-lane{font-size:10px;fill:#8a929c;font-weight:600}
.mp-seed{stroke:#1a6b3c;stroke-width:2.4;stroke-linecap:round}
.mp-seed.s1{stroke:#2f8a55}.mp-seed.s2{stroke:#57a878}
.mp-seed.s3{stroke:#9fc7b1}
.mp-dup{fill:#c7d6e4;stroke:#8fa8be;stroke-width:.8}
.mp-dup.strong{fill:#9fbdd6;stroke:#5b7f9e}
.mp-slab{font-size:9.5px;text-anchor:middle;fill:#5c6670}
.mp-none{font-size:10.5px;fill:#a8b0b8}
@media print{
  .netsvg, .mapsvg{page-break-inside:avoid}
}
"""
