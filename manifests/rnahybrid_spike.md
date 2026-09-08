# RNAhybrid spike (2026-09-08)

Purpose: find out what RNAhybrid actually does before designing the
orchestrator around it.

## Availability

RNAhybrid is packaged in Debian: rnahybrid 2.1.2-8 (trixie/main), which
installs /usr/bin/RNAhybrid, RNAcalibrate and RNAeffective. No Docker
build is needed, and a pinned distribution package is more reproducible
than a hand-built binary.

## Findings

1. Line wrapping is mandatory. A sequence written as one long line loses
   a nucleotide: 1918 nt is reported as 1917, 2000 as 1998. Wrapped at 60
   characters the lengths are exact. Unwrapped input would shift every
   coordinate we derive.

2. -m must be passed. Targets beyond roughly 2000 nt fail with
   "target too long: <name> / Error in nextSQ. Aborting" and produce no
   output at all. With -m 12000 a 10000 nt target runs normally. Many
   human transcripts exceed the default; DICER1 is 10384 nt.

3. -f 2,7 is required for meaningful hits. Without it RNAhybrid ranks by
   folding energy alone and GC-rich non-seed duplexes outrank the real
   site. On PDCD4 3'UTR against hsa-miR-21-5p the true 8mer ranked fifth
   (-18.5 kcal/mol) behind four decoys reaching -23.1. With -f 2,7 it is
   the top hit. RNAhybrid is a scorer for seed-anchored candidates, not a
   finder.

4. P-values are length-dependent and must not be shown as confidence.
   The same duplex gives p = 1.000 in a 1918 nt target and p = 0.227 in a
   30 nt fragment.

5. Positions are 1-based on the sequence supplied. The hit reported at
   227 corresponds to target[226:250] in Python indexing. Transcript
   coordinate = region start + reported position - 1.

6. No hit is reported as mfe 0.0, position 0 and an empty alignment, not
   as absence of output. A naive parser would record it as a
   perfect-energy hit.

7. Speed is roughly 5 microseconds per target nucleotide: 1918 nt in
   19 ms, 10000 nt in 49 ms. A transcriptome-wide run (72 Mnt) is about
   6 minutes per miRNA. Practical, but far beyond a web request, so
   asynchronous job handling is required rather than precautionary.

## Cross-validation

RNAhybrid with -f 2,7 and our own seed analyser independently identify
the same site in PDCD4: target AUAAGCUA at 3'UTR positions 242-249,
transcript 1805-1812, the 8mer for hsa-miR-21-5p.

## Rules for the wrapper

- write wrapped FASTA, always
- pass -m at least the length of the longest target
- pass -f 2,7
- assert the reported target length equals the length supplied, and fail
  loudly if it does not
- capture stderr as well as stdout; "target too long" is invisible to a
  stdout-only reader
- treat mfe 0.0 with position 0 as no hit
- store MFE, not p-value

## Wobble pairing (found when wrapping RNAhybrid as a tool)

-f 2,7 forces a helix over query positions 2-7 but permits G:U wobble
pairs inside it. RNAhybrid therefore reports seed-anchored sites that an
exact Watson-Crick matcher rejects. This is a feature - non-canonical
sites are part of why RNAhybrid is included - but it changes what
"no seed site" means when RNAhybrid is enabled: a gene may carry an
RNAhybrid hit and no seed hit, and that combination is informative
rather than contradictory.

Worked example, hsa-miR-21-5p:

    PDCD4  3'UTR 1790-1813  -18.5  target AUAAGCUA / miRNA UAUUCGAU
                                   all Watson-Crick, the canonical 8mer
    GAPDH  CDS    724-749   -20.6  target UGAGCUG  / miRNA AUUCGAU
                                   two G:U wobbles in the seed helix

The wobble-paired site in GAPDH scores lower (stronger) than the
validated canonical site in PDCD4. Folding energy alone would rank a
housekeeping gene's coding region above the textbook miR-21 target.

This is the concrete justification for per-tool columns and no unified
score: MFE, seed type, conservation and experimental evidence disagree
here, and only showing them separately lets a user see why.
