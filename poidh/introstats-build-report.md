# Mathematics: Introductory statistics — build report

## Source (pinned)
- Book: OpenStax Introductory Statistics 2e (Barbara Illowsky and Susan Dean, OpenStax, Rice University)
- Repo: openstax/osbooks-introductory-statistics-bundle
- Commit: 50ec91749080bb040b57bb40c34337cacc994cba (17 Mar 2026) — the last
  revision before the book moved to CC BY-NC-SA on 19 Mar 2026. A CC licence
  cannot be withdrawn, so the text used is CC BY 4.0. Only the pinned
  revision is used, not later revisions.
- Licence: CC BY 4.0.

## Corpus
- Extractor: tools/packs/extract_openstax_introstats.py (adapted from the
  Prealgebra extractor; same CNXML -> plain-text rules, MathML -> LaTeX)
- File: tools/packs/introstats/corpus.jsonl
- Corpus SHA-256: bd073cdc920228a63f5d5c9b5ab31108136516b161ac1de5293275ed43f7f755
- Rows: 82 documents — all 80 numbered sections of the 13 chapters, plus
  Appendix F (Mathematical Phrases, Symbols, and Formulas) and Appendix H
  (Tables), the formula tables.
- Content: 235 worked examples, 1,881 exercises, glossaries in 38 sections,
  430 tables, 313 figures (captions + alt text kept, images not embedded).
- Excluded: Preface, 13 chapter Introduction pages, Appendices A, B, C, D,
  E, G (Review Exercises, Practice Tests/Final Exams, Data Sets, Group and
  Partner Projects, Solution Sheets, TI-83/84 NOTEs).

## Pack
- Builder: tools/packs/build_introstats_pack.py (stream_pack.py, porter
  unicode61 tokenizer, passages up to 1,200 chars, same settings as the
  Prealgebra pack)
- File: openstax-maths-introstats-0.1.0.fapack
- Pack ID: openstax-maths-introstats (distinct from the Prealgebra pack's
  openstax-maths-stats, so both install and search side by side)
- Title: Mathematics: Introductory statistics
- Version: 0.1.0
- Size: 3,426,659 bytes
- SHA-256: 53171108ec2357f2637ca770224a681052f8b300635eb47305797c855c622afb
- Passages: 1,522
- verify_pack: OK
- Determinism: second build from the pinned corpus is byte-identical
  (same SHA-256).
- ATTRIBUTION.txt inside the archive (listed in the manifest with its hash).

## Answers (keyword search inside the pack, SQLite FTS5 / bm25)
- 8/12 questions put the right section at rank 1, 11/12 in the top 3.
- The 12th (p-value) retrieves Chapter 9 sections that do discuss p-values
  ("Rare Events, the Sample, Decision and Conclusion" — where the p-value
  is introduced); the expected section in the test was arguably the wrong
  pick, not the retrieval.
- Details: introstats-answers.md
