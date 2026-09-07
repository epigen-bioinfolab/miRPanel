# Region enrichment is composition, not signal

Measured on miRBase 23 + MANE v1.5 (19,437 human transcripts).

## Region sizes
3'UTR 34.0 Mnt (47.3%) | CDS 33.9 Mnt (47.1%) | 5'UTR 3.8 Mnt (5.3%)
The two large regions are near-identical in size, so raw counts are
directly comparable without correction.

## 6mer occurrence, 100 human seeds vs shuffled controls
real 3'UTR:CDS = 1.04x | shuffled = 0.94x
Plain 6mer density is equal across regions.

## 7mer+ sites, hsa-miR-21-5p (site TAAGCT)
real = 2.44x | shuffled (n=20) median = 1.62x, range 0.72-2.80
The real seed lies inside the range produced by shuffling the same
six bases. The enrichment is not distinguishable from composition.

## Conclusion
Counting sequence matches cannot demonstrate regional preference.
Functional 3'UTR enrichment is established from repression data, not
match counts. Region counts in this tool must not be read as evidence
of binding preference, and should be reported against a
composition-matched expectation.

Scripts: scripts/composition_control.py
