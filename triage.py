#!/usr/bin/env python3
"""Swarm Triage — deterministic, offline triage of already-fixed public CVEs.

Speedbot Swarm Hackathon entry (mission mission_89fa12eca4ee4b75b6fba593ae895f1f,
lead Nia-Djava).

Scope and rules (hard constraints, by design):
  * Input is a LOCAL JSON dataset of public CVEs that are ALREADY FIXED.
  * No network access, no scanning, no exploitation, no live systems.
  * Standard library only (argparse, json, math, sys, pathlib, datetime).
  * Deterministic: same input file + same --date => byte-identical reports.
    The default report date is the dataset's own verified_date, so a
    re-run months later still reproduces the same files.

Method (fully documented in README.md):
  1. Parse each stored CVSS 3.x vector and RECOMPUTE the base score with
     the FIRST CVSS 3.1 formula. Validation fails if the recomputed score
     does not match the stored NVD score — the dataset must never contain
     a score the vector cannot produce.
  2. Derive two transparent sub-scores from the vector metrics:
       exploitability (0-10) from AV/AC/PR/UI,
       impact         (0-10) from C/I/A.
  3. Triage score (0-10, one decimal):
       triage = 0.60 * cvss_base + 0.25 * exploitability + 0.15 * impact
       + 0.5 if the CVE is listed in CISA KEV (confirmed exploitation),
       capped at 10.0.
  4. Priority: P1 >= 9.0, P2 >= 7.0, P3 >= 4.0, else P4.
     Severity label uses the standard CVSS bands on the triage score.

Usage:
  python3 triage.py --check
      Validate the dataset only (schema, vectors, score recomputation).
  python3 triage.py [--cve CVE-2021-44228]
      Triage all CVEs (or one) and write Markdown reports + summary.
  python3 triage.py --agreement agreement-matrix.md
      Also write the lead-verdict columns of the agreement matrix
      (verifier columns stay empty for the independent verifier).
  python3 triage.py --date 2026-11-17
      Override the report date (default: dataset verified_date).

Exit codes: 0 = ok, 1 = validation failure, 2 = usage error.
"""

import argparse
import json
import math
import sys
from datetime import date
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# CVSS 3.x base-score computation (FIRST specification)
# ---------------------------------------------------------------------------

# Metric weights from the CVSS v3.1 specification.
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}   # scope unchanged
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.50}   # scope changed
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"N": 0.0, "L": 0.22, "H": 0.56}

_METRIC_LABELS = {
    "AV": {"N": "Network", "A": "Adjacent", "L": "Local", "P": "Physical"},
    "AC": {"L": "Low", "H": "High"},
    "PR": {"N": "None", "L": "Low", "H": "High"},
    "UI": {"N": "None", "R": "Required"},
    "S": {"U": "Unchanged", "C": "Changed"},
    "C": {"N": "None", "L": "Low", "H": "High"},
    "I": {"N": "None", "L": "Low", "H": "High"},
    "A": {"N": "None", "L": "Low", "H": "High"},
}


def roundup(value):
    """CVSS 'roundup': smallest number with one decimal >= input.

    Implemented with Decimal so binary float noise (e.g. 8.099999999999998)
    can never push a score over the next tenth. Follows the FIRST reference
    approach of rounding the input to 5 decimals first, then ceiling to
    one decimal.
    """
    d = Decimal(str(value)).quantize(Decimal("0.00001"))
    tenths = (d * 10).to_integral_value(rounding=ROUND_CEILING)
    return float(tenths) / 10.0


def round_half_up(value, ndigits=1):
    """Ordinary rounding, halves away from zero (no banker's rounding)."""
    quantum = Decimal(1).scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(quantum, rounding="ROUND_HALF_UP"))


def parse_vector(vector):
    """Parse a CVSS:3.x vector string into a metric dict.

    Raises ValueError on any malformed input.
    """
    if not isinstance(vector, str):
        raise ValueError("vector must be a string, got %r" % type(vector).__name__)
    parts = vector.split("/")
    if not parts or parts[0] not in ("CVSS:3.0", "CVSS:3.1"):
        raise ValueError("unsupported vector prefix in %r" % vector)
    metrics = {}
    for part in parts[1:]:
        if ":" not in part:
            raise ValueError("malformed vector segment %r in %r" % (part, vector))
        key, val = part.split(":", 1)
        if key not in _METRIC_LABELS:
            raise ValueError("unknown metric %r in %r" % (key, vector))
        if val not in _METRIC_LABELS[key]:
            raise ValueError("unknown value %r for %s in %r" % (val, key, vector))
        metrics[key] = val
    missing = [k for k in ("AV", "AC", "PR", "UI", "S", "C", "I", "A") if k not in metrics]
    if missing:
        raise ValueError("vector %r is missing metrics: %s" % (vector, ", ".join(missing)))
    return metrics


def cvss_base_score(m):
    """Recompute the CVSS 3.x base score from parsed vector metrics."""
    iss = 1.0 - (1.0 - _CIA[m["C"]]) * (1.0 - _CIA[m["I"]]) * (1.0 - _CIA[m["A"]])
    pr_table = _PR_C if m["S"] == "C" else _PR_U
    exploit = 8.22 * _AV[m["AV"]] * _AC[m["AC"]] * pr_table[m["PR"]] * _UI[m["UI"]]
    if m["S"] == "U":
        impact = 6.42 * iss
        if impact <= 0:
            return 0.0
        return roundup(min(impact + exploit, 10.0))
    # Scope changed.
    impact = 7.52 * (iss - 0.029) - 3.25 * math.pow(iss * 0.9731 - 0.02, 13)
    if impact <= 0:
        return 0.0
    return roundup(min(1.08 * (impact + exploit), 10.0))


def severity_label(score):
    """Standard CVSS severity bands."""
    if score >= 9.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 4.0:
        return "Medium"
    if score > 0.0:
        return "Low"
    return "None"


# ---------------------------------------------------------------------------
# Triage sub-scores (transparent, derived only from the vector + KEV flag)
# ---------------------------------------------------------------------------

_AV_T = {"N": 1.0, "A": 0.7, "L": 0.4, "P": 0.1}
_AC_T = {"L": 1.0, "H": 0.5}
_PR_T = {"N": 1.0, "L": 0.7, "H": 0.4}
_UI_T = {"N": 1.0, "R": 0.6}
_CIA_T = {"N": 0.0, "L": 0.5, "H": 1.0}

KEV_BONUS = 0.5
W_CVSS, W_EXPLOIT, W_IMPACT = 0.60, 0.25, 0.15


def exploitability_score(m):
    """0-10: how easy the flaw is to reach and use (AV/AC/PR/UI only)."""
    return round_half_up(
        10.0 * (_AV_T[m["AV"]] + _AC_T[m["AC"]] + _PR_T[m["PR"]] + _UI_T[m["UI"]]) / 4.0
    )


def impact_score(m):
    """0-10: how bad a successful exploit is (C/I/A only)."""
    return round_half_up(10.0 * (_CIA_T[m["C"]] + _CIA_T[m["I"]] + _CIA_T[m["A"]]) / 3.0)


def triage_score(cvss, exploit, impact, kev):
    """Weighted composite + KEV bonus, capped at 10.0, one decimal."""
    raw = W_CVSS * cvss + W_EXPLOIT * exploit + W_IMPACT * impact
    if kev:
        raw += KEV_BONUS
    return min(round_half_up(raw), 10.0)


def priority_for(score):
    if score >= 9.0:
        return "P1"
    if score >= 7.0:
        return "P2"
    if score >= 4.0:
        return "P3"
    return "P4"


# ---------------------------------------------------------------------------
# Dataset validation + triage
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = (
    "cve_id", "name", "title", "vendor", "product", "vuln_class", "cwe",
    "public_disclosure_date", "cvss_version", "cvss_vector", "cvss_score",
    "cvss_severity", "score_source", "description", "affected_versions",
    "fixed_version", "fix_status", "fix_summary", "kev", "poc_public",
    "references",
)


class ValidationError(Exception):
    pass


def load_dataset(path):
    """Load and validate the dataset. Returns (dataset_meta, [entries])."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValidationError("dataset file not found: %s" % path)
    except json.JSONDecodeError as exc:
        raise ValidationError("dataset is not valid JSON: %s" % exc)
    if not isinstance(raw, dict) or "cves" not in raw or "dataset" not in raw:
        raise ValidationError("dataset must be an object with 'dataset' and 'cves'")
    meta = raw["dataset"]
    entries = raw["cves"]
    if not isinstance(entries, list) or not entries:
        raise ValidationError("dataset 'cves' must be a non-empty list")

    seen = set()
    for i, e in enumerate(entries):
        where = "cves[%d]" % i
        if not isinstance(e, dict):
            raise ValidationError("%s is not an object" % where)
        for field in REQUIRED_FIELDS:
            if field not in e:
                raise ValidationError("%s (%s) is missing field %r"
                                      % (where, e.get("cve_id", "?"), field))
        cid = e["cve_id"]
        if cid in seen:
            raise ValidationError("duplicate CVE id: %s" % cid)
        seen.add(cid)
        if e["fix_status"] != "Fixed":
            raise ValidationError("%s: fix_status is %r, dataset is fixed-only"
                                  % (cid, e["fix_status"]))
        if not isinstance(e["kev"], bool) or not isinstance(e["poc_public"], bool):
            raise ValidationError("%s: 'kev' and 'poc_public' must be booleans" % cid)
        if not isinstance(e["references"], list) or not e["references"]:
            raise ValidationError("%s: 'references' must be a non-empty list" % cid)
        for ref in e["references"]:
            if not isinstance(ref, dict) or "label" not in ref or "url" not in ref:
                raise ValidationError("%s: each reference needs 'label' and 'url'" % cid)
            if not (ref["url"].startswith("https://") or ref["url"].startswith("http://")):
                raise ValidationError("%s: reference URL must be http(s): %r"
                                      % (cid, ref["url"]))
        # Vector parse + score recomputation.
        try:
            metrics = parse_vector(e["cvss_vector"])
        except ValueError as exc:
            raise ValidationError("%s: %s" % (cid, exc))
        recomputed = cvss_base_score(metrics)
        if abs(recomputed - float(e["cvss_score"])) > 0.01:
            raise ValidationError(
                "%s: stored CVSS %.1f does not match score recomputed from "
                "vector %s (%.1f). Fix the dataset, never the formula."
                % (cid, e["cvss_score"], e["cvss_vector"], recomputed))
        if severity_label(float(e["cvss_score"])) != e["cvss_severity"]:
            raise ValidationError(
                "%s: stored severity %r does not match CVSS %.1f band %r"
                % (cid, e["cvss_severity"], e["cvss_score"],
                   severity_label(float(e["cvss_score"]))))
    return meta, entries


def triage_entry(entry):
    """Run the full triage for one validated dataset entry."""
    m = parse_vector(entry["cvss_vector"])
    cvss = cvss_base_score(m)
    exploit = exploitability_score(m)
    impact = impact_score(m)
    score = triage_score(cvss, exploit, impact, entry["kev"])
    return {
        "cve_id": entry["cve_id"],
        "name": entry["name"],
        "title": entry["title"],
        "cvss_score": cvss,
        "cvss_severity": severity_label(cvss),
        "cvss_vector": entry["cvss_vector"],
        "cvss_version": entry["cvss_version"],
        "exploitability": exploit,
        "impact": impact,
        "kev": entry["kev"],
        "kev_bonus": KEV_BONUS if entry["kev"] else 0.0,
        "triage_score": score,
        "severity": severity_label(score),
        "priority": priority_for(score),
        "fix_status": entry["fix_status"],
        "metrics": m,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def metric_table(m):
    rows = []
    for key in ("AV", "AC", "PR", "UI", "S", "C", "I", "A"):
        rows.append("| %s | %s | %s |" % (key, m[key], _METRIC_LABELS[key][m[key]]))
    return "\n".join(rows)


def render_report(entry, result, report_date, dataset_meta):
    e = entry
    r = result
    kev_line = ("Yes — listed in CISA KEV"
                + (" (added %s)" % e["kev_date"] if e.get("kev_date") else "")
                + ". Confirmed exploited in the wild at the time of listing.")
    if not e["kev"]:
        kev_line = "No — not listed in CISA KEV as of dataset verification."
    poc_line = "Yes — public proof-of-concept code exists." if e["poc_public"] \
        else "No public proof-of-concept known."
    if e.get("poc_note"):
        poc_line = ("Yes — " if e["poc_public"] else "") + e["poc_note"]
    refs = "\n".join("- [%s](%s)" % (ref["label"], ref["url"]) for ref in e["references"])
    score_note = ("\n\n> **Score note:** %s\n" % e["score_note"]) if e.get("score_note") else ""
    return """# Triage Report — {cve_id} ({name})

| Field | Value |
|---|---|
| CVE | {cve_id} |
| Title | {title} |
| Vendor / Product | {vendor} / {product} |
| Vulnerability class | {vuln_class} |
| CWE | {cwe} — {cwe_name} |
| Public disclosure | {disclosure} |
| Report date | {report_date} |
| Pipeline | swarm-triage v{version} (dataset {ds_version}, verified {ds_verified}) |

## Verdict

| Measure | Value |
|---|---|
| **Triage score** | **{triage:.1f} / 10 ({severity})** |
| **Priority** | **{priority}** |
| CVSS base score ({cvss_version}, {score_source}) | {cvss:.1f} ({cvss_severity}) |
| CVSS vector | `{vector}` |
| CVSS recomputed from vector | {cvss:.1f} — matches stored score |
| Exploitability sub-score | {exploit:.1f} / 10 |
| Impact sub-score | {impact:.1f} / 10 |
| CISA KEV bonus | +{kev_bonus:.1f} |
| Fix status | **{fix_status}** |

Triage score = 0.60 x CVSS + 0.25 x exploitability + 0.15 x impact
+ 0.5 if listed in CISA KEV, capped at 10.0. See `README.md` for the method.

## Description

{description}
{score_note}
## Impact

{impact_text}

Impact sub-score **{impact:.1f} / 10** — confidentiality {c}, integrity {i}, availability {a}
(scope: {scope}).

## Exploitability

{exploit_text}

Exploitability sub-score **{exploit:.1f} / 10** — attack vector {av},
complexity {ac}, privileges {pr}, user interaction {ui}.

- **CISA KEV:** {kev_line}
- **Public PoC:** {poc_line}

## Fix

- **Status:** {fix_status} — vendor patch available, no live exploitation is
  in scope for this report (already-fixed public CVE only).
- **Fixed version:** {fixed_version}
- **Affected:** {affected}

{fix_summary}

## CVSS vector breakdown

| Metric | Value | Meaning |
|---|---|---|
{metric_table}

## References (public sources only)

{refs}

---

*Generated deterministically by `triage.py` from `data/cves.json`.
No live systems were scanned or tested. All data is public and already fixed.*
""".format(
        cve_id=e["cve_id"], name=e["name"], title=e["title"],
        vendor=e["vendor"], product=e["product"], vuln_class=e["vuln_class"],
        cwe=e["cwe"], cwe_name=e["cwe_name"],
        disclosure=e["public_disclosure_date"], report_date=report_date,
        version=VERSION, ds_version=dataset_meta.get("version", "?"),
        ds_verified=dataset_meta.get("verified_date", "?"),
        triage=r["triage_score"], severity=r["severity"], priority=r["priority"],
        cvss_version=e["cvss_version"], score_source=e["score_source"],
        cvss=r["cvss_score"], cvss_severity=r["cvss_severity"],
        vector=e["cvss_vector"], exploit=r["exploitability"],
        impact=r["impact"], kev_bonus=r["kev_bonus"], fix_status=e["fix_status"],
        description=e["description"], score_note=score_note,
        impact_text=impact_text(e), c=r["metrics"]["C"], i=r["metrics"]["I"],
        a=r["metrics"]["A"],
        scope=_METRIC_LABELS["S"][r["metrics"]["S"]].lower(),
        exploit_text=exploit_text(e, r),
        av=_METRIC_LABELS["AV"][r["metrics"]["AV"]].lower(),
        ac=_METRIC_LABELS["AC"][r["metrics"]["AC"]].lower(),
        pr=_METRIC_LABELS["PR"][r["metrics"]["PR"]].lower(),
        ui=_METRIC_LABELS["UI"][r["metrics"]["UI"]].lower(),
        kev_line=kev_line, poc_line=poc_line,
        fixed_version=e["fixed_version"], affected=e["affected_versions"],
        fix_summary=e["fix_summary"], metric_table=metric_table(r["metrics"]),
        refs=refs,
    )


def impact_text(entry):
    m = parse_vector(entry["cvss_vector"])
    c, i, a = m["C"], m["I"], m["A"]
    if c == "H" and i == "H" and a == "H":
        level = "Total loss of confidentiality, integrity and availability"
    elif c == "H" and i == "N" and a == "N":
        level = "Confidentiality loss only — sensitive data can be read, but data is not modified and the service stays up"
    elif c == "N" and i == "N" and a == "H":
        level = "Availability loss only — the service can be taken down, but no data is read or modified"
    else:
        parts = []
        if c != "N":
            parts.append("confidentiality " + _METRIC_LABELS["C"][c].lower())
        if i != "N":
            parts.append("integrity " + _METRIC_LABELS["I"][i].lower())
        if a != "N":
            parts.append("availability " + _METRIC_LABELS["A"][a].lower())
        level = "Partial impact: " + ", ".join(parts)
    scope = "changed scope — impact escapes the vulnerable component" \
        if m["S"] == "C" else "unchanged scope — impact stays within the component"
    return "%s (%s)." % (level, scope)


def exploit_text(entry, result):
    m = result["metrics"]
    bits = []
    bits.append("reachable remotely over the network"
                if m["AV"] == "N" else "attack vector: %s" % _METRIC_LABELS["AV"][m["AV"]].lower())
    bits.append("attack complexity %s" % _METRIC_LABELS["AC"][m["AC"]].lower())
    bits.append("privileges required: %s" % _METRIC_LABELS["PR"][m["PR"]].lower())
    bits.append("user interaction: %s" % _METRIC_LABELS["UI"][m["UI"]].lower())
    return "Exploitable: " + ", ".join(bits) + "."


def render_summary(results, report_date, dataset_meta):
    rows = []
    for r in results:
        rows.append("| %s | %s | %.1f (%s) | %.1f | %.1f | %.1f | %s | %s | %s |" % (
            r["cve_id"], r["name"], r["cvss_score"], r["cvss_severity"],
            r["exploitability"], r["impact"], r["triage_score"],
            r["severity"], r["priority"],
            "Yes" if r["kev"] else "No"))
    table = "\n".join(rows)
    counts = {}
    for r in results:
        counts[r["priority"]] = counts.get(r["priority"], 0) + 1
    dist = ", ".join("%s: %d" % (p, counts.get(p, 0)) for p in ("P1", "P2", "P3", "P4"))
    return """# Swarm Triage — Summary

- **Report date:** {report_date}
- **Pipeline:** swarm-triage v{version}
- **Dataset:** {ds_name} v{ds_version} (verified {ds_verified})
- **CVEs triaged:** {n}
- **Priority distribution:** {dist}

| CVE | Name | CVSS | Exploitability | Impact | Triage | Severity | Priority | KEV |
|---|---|---|---|---|---|---|---|---|
{table}

## Method (one line)

Triage = 0.60 x CVSS + 0.25 x exploitability + 0.15 x impact + 0.5 if in CISA KEV
(capped at 10.0). Priority: P1 >= 9.0, P2 >= 7.0, P3 >= 4.0, else P4.
Full method, scope rules and limitations: see `README.md`.

## Files

One Markdown report per CVE in this directory (`<CVE-ID>.md`).
Machine-readable results: `summary.json`.
""".format(
        report_date=report_date, version=VERSION,
        ds_name=dataset_meta.get("name", "?"), ds_version=dataset_meta.get("version", "?"),
        ds_verified=dataset_meta.get("verified_date", "?"), n=len(results),
        dist=dist, table=table)


def render_agreement(results, report_date):
    rows = []
    for r in results:
        rows.append(
            "| %s | %s %.1f (%s) | Triage %.1f, CVSS %.1f, KEV %s, exploitability %.1f, impact %.1f |  |  |  | |"
            % (r["cve_id"], r["priority"], r["triage_score"], r["severity"],
               r["triage_score"], r["cvss_score"], "yes" if r["kev"] else "no",
               r["exploitability"], r["impact"]))
    return """# Agreement Matrix — Swarm Triage

Lead verdicts were produced by `triage.py` v{version} on {report_date} from
`data/cves.json`. The verifier runs the same pipeline independently and fills
in the verifier columns. A row **agrees** only when both sides reach the same
priority (P1–P4) from the same dataset — if they differ, the row stays open
until the discrepancy is resolved (usually a dataset or formula difference,
never a silent override).

| CVE | Lead verdict | Lead rationale (triage inputs) | Verifier verdict | Verifier rationale | Agreement | Notes |
|---|---|---|---|---|---|---|
{table}

## Rules

1. The verifier re-runs `python3 triage.py` on their own copy of this repo
   and compares `reports/summary.json` with the lead's, byte for byte
   (same `--date`).
2. Agreement = same priority per CVE. A different triage score with the same
   priority still counts as agreement, but the difference must be noted.
3. The lead column is never edited after the run. Corrections go through a
   new dataset version and a fresh run.
4. Empty verifier cells mean "not yet verified" — never "agreed".
""".format(version=VERSION, report_date=report_date, table="\n".join(rows))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="triage.py",
        description="Swarm Triage: deterministic offline triage of already-fixed "
                    "public CVEs (stdlib only, no network, no scanning).")
    p.add_argument("--input", default="data/cves.json",
                   help="dataset JSON file (default: data/cves.json)")
    p.add_argument("--out", default="reports",
                   help="output directory for reports (default: reports)")
    p.add_argument("--cve", default=None,
                   help="triage a single CVE id only, e.g. CVE-2021-44228")
    p.add_argument("--check", action="store_true",
                   help="validate the dataset only; write no files")
    p.add_argument("--agreement", default=None, metavar="PATH",
                   help="also write agreement-matrix.md to PATH (lead columns filled, "
                        "verifier columns empty)")
    p.add_argument("--date", default=None,
                   help="report date YYYY-MM-DD (default: dataset verified_date)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        meta, entries = load_dataset(args.input)
    except ValidationError as exc:
        print("VALIDATION FAILED: %s" % exc, file=sys.stderr)
        return 1

    if args.check:
        print("OK: %d CVEs validated — all vectors parse, all CVSS scores "
              "recompute from their vectors, all fixes confirmed present."
              % len(entries))
        return 0

    report_date = args.date or meta.get("verified_date") or date.today().isoformat()
    try:
        date.fromisoformat(report_date)
    except ValueError:
        print("error: --date must be YYYY-MM-DD, got %r" % report_date, file=sys.stderr)
        return 2

    if args.cve:
        wanted = args.cve.strip().upper()
        entries = [e for e in entries if e["cve_id"] == wanted]
        if not entries:
            print("error: %s is not in the dataset" % wanted, file=sys.stderr)
            return 2

    entries = sorted(entries, key=lambda e: e["cve_id"])
    results = [triage_entry(e) for e in entries]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for entry, result in zip(entries, results):
        (out_dir / ("%s.md" % entry["cve_id"])).write_text(
            render_report(entry, result, report_date, meta), encoding="utf-8")
    (out_dir / "summary.md").write_text(
        render_summary(results, report_date, meta), encoding="utf-8")
    summary_json = {
        "pipeline": "swarm-triage",
        "pipeline_version": VERSION,
        "report_date": report_date,
        "dataset": {
            "name": meta.get("name"),
            "version": meta.get("version"),
            "verified_date": meta.get("verified_date"),
        },
        "method": {
            "formula": "triage = 0.60*cvss + 0.25*exploitability + 0.15*impact + 0.5 if KEV, capped at 10.0",
            "priority": "P1 >= 9.0, P2 >= 7.0, P3 >= 4.0, else P4",
        },
        "results": [
            {k: v for k, v in r.items() if k != "metrics"}
            for r in results
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.agreement:
        Path(args.agreement).write_text(
            render_agreement(results, report_date), encoding="utf-8")

    print("CVE          Triage  Severity  Priority  CVSS   KEV")
    for r in results:
        print("%-12s %-6.1f  %-8s  %-8s  %-6.1f %s" % (
            r["cve_id"], r["triage_score"], r["severity"], r["priority"],
            r["cvss_score"], "yes" if r["kev"] else "no"))
    print("\nWrote %d report(s) + summary.md + summary.json to %s/"
          % (len(results), out_dir))
    if args.agreement:
        print("Wrote agreement matrix to %s" % args.agreement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
