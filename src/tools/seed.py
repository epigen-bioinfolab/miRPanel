def clean_sequence(seq: str) -> str:
    """Normalize any input sequence: uppercase, no whitespace, RNA (U) -> DNA (T)."""
    seq = "".join(seq.split()).upper()
    return seq.replace("U", "T")


def get_seed(mirna: str) -> str:
    """Return the seed region: nucleotides 2-8 of the miRNA (7 nt from the 5' end)."""
    mirna = clean_sequence(mirna)
    if len(mirna) < 8:
        raise ValueError(f"miRNA too short for a seed: {len(mirna)} nt, need at least 8")
    return mirna[1:8]


COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}


def reverse_complement(seq: str) -> str:
    """Return the reverse complement: the pattern a target site must have to pair."""
    seq = clean_sequence(seq)
    return "".join(COMPLEMENT[base] for base in reversed(seq))


def get_6mer_site(mirna: str) -> str:
    """The 6mer target site: reverse complement of miRNA positions 2-7."""
    mirna = clean_sequence(mirna)
    return reverse_complement(mirna[1:7])


def find_all(pattern: str, sequence: str) -> list[int]:
    """Return 0-based start positions of every occurrence, including overlaps."""
    positions = []
    start = sequence.find(pattern)
    while start != -1:
        positions.append(start)
        start = sequence.find(pattern, start + 1)
    return positions


def classify_site(mirna: str, target: str, position: int) -> str:
    """Grade a 6mer hit at `position` as 8mer, 7mer-m8, 7mer-A1 or 6mer."""
    mirna = clean_sequence(mirna)
    target = clean_sequence(target)
    if len(mirna) < 8:
        raise ValueError(f"miRNA too short: {len(mirna)} nt, need at least 8")
    m8_base = COMPLEMENT[mirna[7]]
    has_m8 = position > 0 and target[position - 1] == m8_base
    has_a1 = position + 6 < len(target) and target[position + 6] == "A"
    if has_m8 and has_a1:
        return "8mer"
    if has_m8:
        return "7mer-m8"
    if has_a1:
        return "7mer-A1"
    return "6mer"


def find_sites(
    mirna: str,
    target: str,
    mirna_id: str = "query_miRNA",
    target_id: str = "query_target",
    region: str = "3UTR",
) -> list[dict]:
    """Scan a target for seed sites; return one standardized record per site."""
    mirna = validate_sequence(mirna)
    target = validate_sequence(target)
    site = get_6mer_site(mirna)
    records = []
    for pos in find_all(site, target):
        site_type = classify_site(mirna, target, pos)
        records.append({
            "mirna": mirna_id,
            "target": target_id,
            "region": region,
            "tool": "seed",
            "site_type": site_type,
            "position": pos + 1,
            "score": site_type,
            "score_type": "site_type",
            "low_confidence": site_type == "6mer",
        })
    return records


VALID_BASES = set("ATGCN")


def validate_sequence(seq: str) -> str:
    """Strip a FASTA header if present, clean, and reject anything that is not DNA/RNA."""
    if seq.lstrip().startswith(">"):
        seq = "\n".join(seq.split("\n")[1:])
    seq = clean_sequence(seq)
    if not seq:
        raise ValueError("empty sequence")
    bad = sorted(set(seq) - VALID_BASES)
    if bad:
        raise ValueError(f"invalid characters in sequence: {', '.join(bad)}")
    return seq
