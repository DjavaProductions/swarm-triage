# Swarm Triage

Deterministic, offline triage pipeline for **already-fixed, publicly disclosed**
vulnerabilities — entry for the **Speedbot Swarm Hackathon**
(mission `mission_89fa12eca4ee4b75b6fba593ae895f1f`, lead Nia-Djava).

It takes a bundled local dataset of 10 famous fixed CVEs, recomputes every
CVSS base score from its vector (so a wrong score can never slip through),
derives transparent exploitability / impact sub-scores, and produces one
structured triage report per CVE plus a summary and an agreement matrix for
independent verification.

## Scope rules (non-negotiable)

- **Already-fixed public CVEs only.** Every entry in `data/cves.json` has a
  vendor patch and a public disclosure. No zero-days, no unpublished flaws.
- **No live exploitation, no scanning.** The pipeline reads one local JSON
  file and writes Markdown/JSON. It makes no network requests and touches no
  live system. There is no exploit code anywhere in this repo.
- **Public data only.** Every CVSS vector, score and reference comes from
  NVD (NIST), vendor advisories, or the CISA KEV catalog — all linked per CVE.
- **Deterministic.** Same input + same `--date` => byte-identical output.
  The default report date is the dataset's own `verified_date`, so a re-run
  months later still reproduces the same files.

## Repository layout

```
swarm-triage/
├── triage.py            # the pipeline (Python stdlib only, offline)
├── data/
│   └── cves.json        # dataset: 10 fixed public CVEs + raw public data
├── reports/
│   ├── CVE-*.md         # one triage report per CVE (generated)
│   ├── summary.md       # index table (generated)
│   └── summary.json     # machine-readable results (generated)
├── agreement-matrix.md  # lead verdicts filled; verifier columns empty
├── demo.sh              # end-to-end demo on one CVE
├── README.md            # this file
└── LICENSE              # MIT
```

## The 10 CVEs

| CVE | Name | CVSS | Triage | Priority | KEV |
|---|---|---|---|---|---|
| CVE-2021-44228 | Log4Shell | 10.0 Critical | 10.0 | P1 | Yes |
| CVE-2014-0160 | Heartbleed | 7.5 High | 8.0 | P2 | Yes |
| CVE-2017-0144 | EternalBlue | 8.1 High | 9.1 | P1 | Yes |
| CVE-2021-34527 | PrintNightmare | 8.8 High | 9.6 | P1 | Yes |
| CVE-2022-22965 | Spring4Shell | 9.8 Critical | 10.0 | P1 | Yes |
| CVE-2023-44487 | HTTP/2 Rapid Reset | 7.5 High | 8.0 | P2 | Yes |
| CVE-2024-3094 | xz backdoor | 10.0 Critical | 10.0 | P1 | No |
| CVE-2021-26855 | ProxyLogon | 9.8 Critical | 10.0 | P1 | Yes |
| CVE-2020-1472 | Zerologon | 10.0 Critical | 10.0 | P1 | Yes |
| CVE-2019-0708 | BlueKeep | 9.8 Critical | 10.0 | P1 | Yes |

Classes covered: remote code execution (5), privilege escalation (2),
information disclosure (1), denial of service (1), supply-chain backdoor (1).
All scores are NVD (NIST) CVSS 3.x base scores, verified 2026-11-17.

## Method

### 1. CVSS recomputation (validation gate)

Each stored CVSS base score is **recomputed from its vector** using the
FIRST CVSS 3.1 formula (including the spec's `roundup` rule, implemented with
`Decimal` so float noise can never push a score over the next tenth).
`--check` fails if any stored score differs from the recomputed one — the
dataset must never contain a score its vector cannot produce.

Why this matters: CVSS involves analyst judgment. The same CVE can be scored
differently by different parties (e.g. CVE-2020-1472: NVD 10.0 vs Microsoft
5.5; CVE-2021-26855: NVD 9.8 vs Microsoft 9.1). This dataset uses the NVD
score throughout and records known divergences in each entry's `score_note`,
so the choice is explicit and auditable.

### 2. Sub-scores (from the vector only)

- **Exploitability (0–10):** mean of AV / AC / PR / UI weights.
  AV: N=1.0, A=0.7, L=0.4, P=0.1 · AC: L=1.0, H=0.5 ·
  PR: N=1.0, L=0.7, H=0.4 · UI: N=1.0, R=0.6.
- **Impact (0–10):** mean of C / I / A weights (H=1.0, L=0.5, N=0.0).

### 3. Triage score (0–10, one decimal)

```
triage = 0.60 * cvss_base + 0.25 * exploitability + 0.15 * impact
         + 0.5 if listed in CISA KEV, capped at 10.0
```

CVSS dominates (it already encodes exploitability and impact); the sub-scores
break ties between CVEs with the same CVSS — e.g. Heartbleed and Rapid Reset
both score CVSS 7.5, but their impact sub-scores (3.3, confidentiality-only /
availability-only) keep them at triage 8.0 while full-impact RCEs at the same
CVSS would rank higher. The KEV bonus rewards *confirmed* exploitation, not
speculation.

### 4. Priority

| Triage score | Priority |
|---|---|
| >= 9.0 | P1 |
| >= 7.0 | P2 |
| >= 4.0 | P3 |
| < 4.0 | P4 |

Severity labels use the standard CVSS bands (Critical >= 9.0, High >= 7.0,
Medium >= 4.0, Low > 0).

## Reproduce (step by step)

Requirements: Python 3.8+ only. No dependencies, no install step, no network.

```bash
# 1. Get the code (or copy this directory)
git clone <repo-url>          # or: cd swarm-triage

# 2. Validate the dataset (schema, vectors, score recomputation)
python3 triage.py --check
# expected: OK: 10 CVEs validated — all vectors parse, all CVSS scores
#           recompute from their vectors, all fixes confirmed present.

# 3. Run the full pipeline
python3 triage.py --agreement agreement-matrix.md
# expected: a table of 10 CVEs (8x P1, 2x P2) and
#           "Wrote 10 report(s) + summary.md + summary.json to reports/"

# 4. Verify determinism (optional but recommended)
python3 triage.py --out /tmp/swarm-triage-check
diff -r reports /tmp/swarm-triage-check
# expected: no differences (byte-identical output)
```

Single-CVE run (also what `demo.sh` does):

```bash
python3 triage.py --cve CVE-2021-44228 --out /tmp/demo
cat /tmp/demo/CVE-2021-44228.md
```

Useful flags: `--input` (dataset path), `--out` (report directory),
`--date YYYY-MM-DD` (override report date; default is the dataset's
`verified_date`, which is what makes output byte-identical across re-runs),
`--agreement PATH` (write the agreement matrix).

Exit codes: `0` ok, `1` dataset validation failure, `2` usage error.

## Expected output

- `reports/CVE-<id>.md` — one per CVE: verdict box (triage score, priority,
  CVSS, sub-scores, KEV, fix status), description, impact, exploitability,
  fix summary, full CVSS vector breakdown, public references.
- `reports/summary.md` — index table of all 10 CVEs + priority distribution.
- `reports/summary.json` — same results machine-readable (sorted keys).
- `agreement-matrix.md` — lead verdicts pre-filled; verifier columns empty.

## Independent verification (agreement matrix)

The verifier — a second agent with no shared state — re-runs the pipeline on
their own copy and fills in the verifier columns of `agreement-matrix.md`:

1. `python3 triage.py --check` must pass on their copy.
2. `python3 triage.py --out /tmp/verify` then `diff -r reports /tmp/verify`
   must show no differences (same `--date`).
3. Agreement = same **priority** per CVE. A different triage score with the
   same priority still counts as agreement, but must be noted.
4. Empty verifier cells mean "not yet verified" — never "agreed".
5. The lead column is never edited after the run. Corrections go through a
   new dataset version and a fresh run.

## Limitations (honest)

- **CVSS is not risk.** It measures a flaw's technical severity in the
  abstract — not whether the product runs in your environment, is reachable,
  or is being exploited against you. The KEV bonus is the only
  exploitation signal, and it is binary.
- **The triage weights are a choice, not a standard.** 0.60/0.25/0.15 + 0.5
  KEV is documented, deterministic and reproducible — but it is our weighting,
  and a different team could reasonably pick another. The formula is printed
  in every report so the choice is auditable.
- **Dataset is a fixed snapshot (v1.0.0, verified 2026-11-17).** CVEs do not
  change, but KEV membership and vendor guidance can. A re-verification
  updates `verified_date` and bumps the dataset version.
- **Famous-CVE bias.** All 10 are well-known, high-severity flaws — the
  dataset demonstrates the pipeline, it does not represent the severity
  distribution of CVEs in general (8x P1 / 2x P2 here).
- **No asset context.** The pipeline triages vulnerabilities, not assets.
  Real prioritization multiplies this by exposure and asset criticality,
  which this tool deliberately does not invent.

## License

MIT — see `LICENSE`.
