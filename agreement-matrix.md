# Agreement Matrix — Swarm Triage

Lead verdicts were produced by `triage.py` v1.0.0 on 2026-11-17 from
`data/cves.json`. The verifier runs the same pipeline independently and fills
in the verifier columns. A row **agrees** only when both sides reach the same
priority (P1–P4) from the same dataset — if they differ, the row stays open
until the discrepancy is resolved (usually a dataset or formula difference,
never a silent override).

| CVE | Lead verdict | Lead rationale (triage inputs) | Verifier verdict | Verifier rationale | Agreement | Notes |
|---|---|---|---|---|---|---|
| CVE-2014-0160 | P2 8.0 (High) | Triage 8.0, CVSS 7.5, KEV yes, exploitability 10.0, impact 3.3 |  |  |  | |
| CVE-2017-0144 | P1 9.1 (Critical) | Triage 9.1, CVSS 8.1, KEV yes, exploitability 8.8, impact 10.0 |  |  |  | |
| CVE-2019-0708 | P1 10.0 (Critical) | Triage 10.0, CVSS 9.8, KEV yes, exploitability 10.0, impact 10.0 |  |  |  | |
| CVE-2020-1472 | P1 10.0 (Critical) | Triage 10.0, CVSS 10.0, KEV yes, exploitability 10.0, impact 10.0 |  |  |  | |
| CVE-2021-26855 | P1 10.0 (Critical) | Triage 10.0, CVSS 9.8, KEV yes, exploitability 10.0, impact 10.0 |  |  |  | |
| CVE-2021-34527 | P1 9.6 (Critical) | Triage 9.6, CVSS 8.8, KEV yes, exploitability 9.3, impact 10.0 |  |  |  | |
| CVE-2021-44228 | P1 10.0 (Critical) | Triage 10.0, CVSS 10.0, KEV yes, exploitability 10.0, impact 10.0 |  |  |  | |
| CVE-2022-22965 | P1 10.0 (Critical) | Triage 10.0, CVSS 9.8, KEV yes, exploitability 10.0, impact 10.0 |  |  |  | |
| CVE-2023-44487 | P2 8.0 (High) | Triage 8.0, CVSS 7.5, KEV yes, exploitability 10.0, impact 3.3 |  |  |  | |
| CVE-2024-3094 | P1 10.0 (Critical) | Triage 10.0, CVSS 10.0, KEV no, exploitability 10.0, impact 10.0 |  |  |  | |

## Rules

1. The verifier re-runs `python3 triage.py` on their own copy of this repo
   and compares `reports/summary.json` with the lead's, byte for byte
   (same `--date`).
2. Agreement = same priority per CVE. A different triage score with the same
   priority still counts as agreement, but the difference must be noted.
3. The lead column is never edited after the run. Corrections go through a
   new dataset version and a fresh run.
4. Empty verifier cells mean "not yet verified" — never "agreed".
