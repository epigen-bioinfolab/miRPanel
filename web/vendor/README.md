# Vendored third-party code

## vis-network 10.1.2

    web/vendor/vis-network.min.js

The network rendering library, the same engine behind R's visNetwork.
Downloaded from npm (`npm pack vis-network@10.1.2`), standalone UMD build,
which defines the global `vis`.

Vendored rather than loaded from a CDN for three reasons: the tool must work
on a machine with no internet access, a CDN outage must not break a page that
is otherwise entirely self-hosted, and a pinned local copy is the only version
claim that stays true.

Licensed under MIT **or** Apache-2.0 (see LICENSE-MIT and LICENSE-APACHE-2.0).
Copyright (c) 2011-2017 Almende B.V. and 2017-2019 visjs contributors.

The library's own stylesheet is **not** vendored: it is 220 KB, almost all of
it for editing toolbars and images this tool does not use. The few rules the
tooltip needs are written by hand in `scripts/build_page.py`.
