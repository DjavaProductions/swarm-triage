# Swarm Triage — Summary

- **Report date:** 2026-11-17
- **Pipeline:** swarm-triage v1.0.0
- **Dataset:** swarm-triage-cve-dataset v1.0.0 (verified 2026-11-17)
- **CVEs triaged:** 10
- **Priority distribution:** P1: 8, P2: 2, P3: 0, P4: 0

| CVE | Name | CVSS | Exploitability | Impact | Triage | Severity | Priority | KEV |
|---|---|---|---|---|---|---|---|---|
| CVE-2014-0160 | Heartbleed | 7.5 (High) | 10.0 | 3.3 | 8.0 | High | P2 | Yes |
| CVE-2017-0144 | EternalBlue | 8.1 (High) | 8.8 | 10.0 | 9.1 | Critical | P1 | Yes |
| CVE-2019-0708 | BlueKeep | 9.8 (Critical) | 10.0 | 10.0 | 10.0 | Critical | P1 | Yes |
| CVE-2020-1472 | Zerologon | 10.0 (Critical) | 10.0 | 10.0 | 10.0 | Critical | P1 | Yes |
| CVE-2021-26855 | ProxyLogon | 9.8 (Critical) | 10.0 | 10.0 | 10.0 | Critical | P1 | Yes |
| CVE-2021-34527 | PrintNightmare | 8.8 (High) | 9.3 | 10.0 | 9.6 | Critical | P1 | Yes |
| CVE-2021-44228 | Log4Shell | 10.0 (Critical) | 10.0 | 10.0 | 10.0 | Critical | P1 | Yes |
| CVE-2022-22965 | Spring4Shell | 9.8 (Critical) | 10.0 | 10.0 | 10.0 | Critical | P1 | Yes |
| CVE-2023-44487 | HTTP/2 Rapid Reset | 7.5 (High) | 10.0 | 3.3 | 8.0 | High | P2 | Yes |
| CVE-2024-3094 | xz backdoor | 10.0 (Critical) | 10.0 | 10.0 | 10.0 | Critical | P1 | No |

## Method (one line)

Triage = 0.60 x CVSS + 0.25 x exploitability + 0.15 x impact + 0.5 if in CISA KEV
(capped at 10.0). Priority: P1 >= 9.0, P2 >= 7.0, P3 >= 4.0, else P4.
Full method, scope rules and limitations: see `README.md`.

## Files

One Markdown report per CVE in this directory (`<CVE-ID>.md`).
Machine-readable results: `summary.json`.
