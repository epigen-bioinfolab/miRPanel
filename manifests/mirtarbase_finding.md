# miRTarBase 10.0: loading and name reconciliation

Measured 2026-09-08.

## Source

miRTarBase release 10.0, from awi.cuhk.edu.cn/miRTarBase. The download page
is headed "Release 11.0", but every link serves /10.0/ files and /11.0/
returns 404, so 10.0 is what is loaded. Licence: public domain, with a
warranty disclaimer and no redistribution restriction.

Files used: hsa_MTI.csv (337103345 bytes, human interactions),
MicroRNA_Target_Sites.csv (curated target site sequences), and
miRTarBase_SE_WR.csv (strong evidence, kept for reference only).

## Evidence tiers

Human rows in hsa_MTI.csv: 4004479

| Support Type | rows |
|---|---|
| Functional MTI (Weak) | 3981769 |
| Functional MTI | 18044 |
| Non-Functional MTI | 4236 |
| Non-Functional MTI (Weak) | 430 |

Non-Functional MTI records a published finding that the miRNA does NOT
regulate the gene. It is never displayed as validated. The loader refuses
to run if a Support Type outside these four appears.

## Name reconciliation

miRTarBase identifies miRNAs by name, not accession, and its CLIP-seq data
comes from 2010-2013 papers using pre-suffix names (hsa-miR-122 rather than
hsa-miR-122-5p). miRBase serves only releases 20-22, and 299 of these bare
names have both arms annotated in Release 23, so the arm cannot be inferred.

Historical name-to-accession pairs were exported from miRBaseConverter
1.34.0 (Bioconductor 3.22, R 4.5.0), covering 22 miRBase releases from v6
(2005) to v22 (2018): 3486 unique human pairs, 774 of them new.

| stage | unresolved evidence rows |
|---|---|
| miRBase 22 aliases only | 899902 (22.5%) |
| plus releases 21 and 20 | 899902 |
| plus miRBaseConverter v6-v22 | 184409 (4.6%) |

Of the 184409 residual, 149049 rows (83 miRNAs) are miRNAs deleted in
miRBase Release 23. These are correctly unresolvable and are reported as
retired rather than as absent. 18 human aliases map to more than one
accession across releases; the resolver reports these as ambiguous and
does not guess.

## Loaded

- mirtarbase_evidence 4004479 rows
- mirtarbase_sites 669164 rows (target sites are sequences, not
  coordinates, so they can be located in our own MANE transcripts)
- mirtarbase 1612045 summary pairs: 8575 with strong functional support,
  2120 with contradicting strong evidence, 278452 carrying a curated site
