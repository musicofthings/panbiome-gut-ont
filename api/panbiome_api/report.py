"""Report data for a finished run: run-level QC and per-sample results, read from the files the workflow writes."""

import csv
import io
import json
import math
from collections.abc import Callable

SPECIES_ROWS = 200
TABLE_ROWS = 500


def _value(v: str):
    if v in ("", "NA", "None", "nan"):
        return None
    if v in ("True", "False"):
        return v == "True"
    # Keep IDs such as "001" as text
    if len(v) > 1 and v[0] == "0" and v[1] != ".":
        return v
    try:
        f = float(v)
    except ValueError:
        return v
    if not math.isfinite(f):
        return v
    return int(f) if f.is_integer() and "." not in v and "e" not in v.lower() else f


def parse_tsv(text: str | None) -> list[dict] | None:
    if text is None:
        return None
    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        lines[0] = lines[0][1:]
    rows = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="\t")
    return [{k: _value(v) for k, v in row.items()} for row in rows]


def run_summary(read: Callable[[str], str | None], samples: list[str]) -> dict:
    """read(path) returns the text of results/<run>/<path>, or None."""

    def js(path):
        text = read(path)
        return json.loads(text) if text else None

    return {
        "summary": js("run/qc_summary.json"),
        "qc": parse_tsv(read("run/qc_summary.tsv")),
        "control": js("run/controls/control_status.json"),
        "alpha": parse_tsv(read("run/diversity/alpha_diversity.tsv")),
        "samples": samples,
    }


def sample_report(read: Callable[[str], str | None], sample: str) -> dict:
    base = f"samples/{sample}/"
    p = f"{base}{{}}/{sample}.{{}}"

    def js(path):
        text = read(path)
        return json.loads(text) if text else None

    def tsv(path, limit=TABLE_ROWS):
        rows = parse_tsv(read(path))
        return None if rows is None else {"rows": rows[:limit], "total": len(rows)}

    species = parse_tsv(read(p.format("taxonomy", "species.tsv")))
    if species is not None:
        kept = [r for r in species if r.get("kept")]
        kept.sort(key=lambda r: r.get("final_rel_abundance") or 0, reverse=True)
        species = {"rows": kept[:SPECIES_ROWS], "kept": len(kept), "candidates": len(species)}

    amr = tsv(p.format("resistance", "amr_linked.tsv")) or tsv(p.format("resistance", "amrfinder.tsv"))
    plasmids = parse_tsv(read(p.format("resistance", "plasmid_summary.tsv")))
    return {
        "sample": sample,
        "raw": js(p.format("qc", "raw.stats.json")),
        "filtered": js(p.format("qc", "filtered.stats.json")),
        "host": js(p.format("qc", "host.json")),
        "taxa_summary": js(p.format("taxonomy", "taxa_summary.json")),
        "species": species,
        "watchlist": tsv(p.format("taxonomy", "watchlist.tsv")),
        "bins": tsv(p.format("resistance", "mags.tsv")),
        "amr": amr,
        "plasmids": None
        if plasmids is None
        else {"total": len(plasmids), "rows": sorted(plasmids, key=lambda r: -(r.get("plasmid_score") or 0))[:50]},
        "function_targets": tsv(p.format("function", "function_targets.tsv")),
        "modules": tsv(p.format("function", "function_module.tsv"), 30),
    }
