# Audit: Zest CLMM venue in Jing stx-usdcx router v6 (diff v5-5 -> v6)

- **Target:** `github.com/Rapha-btc/jing-contracts-v3` @ `9dab9bd`,
  `contracts/stx-usdcx/swap-router-stx-usdcx-jing-v6.clar`
- **Pin verified:** `sha256 d974ea913ef9e6bfd575af55125ca71b59310dd1b93c568a138ebf44e672e502`
  (matches the bounty pin; `git rev-parse HEAD` = `9dab9bd…`).
- **Diff:** +361 / -6 vs `swap-router-stx-usdcx-jing-v5-5.clar` (same folder). All new
  code is Zest surface; every helper outside the diff (`limit-min`, `dust-left`,
  `scale-min`, `with-fallback`, `fallback-residual`, `dlmm-stage`, `dlmm-pick`,
  `dlmm-out-step`, `cp-stage`, `amm-floor`, `leg-stx`, `leg-usdcx`, `jing-swap`,
  `jing-size`, `book-limit`) is byte-identical to v5-5 — confirmed with
  `git diff --no-index`.
- **Bounty:** AIBTC `mwaypr0sa4d1d6ca1f6a`, "Audit 6k: Zest CLMM venue in Jing
  stx-usdcx router v6 (diff vs v5-5 only)", deadline 24 Nov 2026 23:59 UTC.
- **Method:** full line-by-line diff read; exact-integer Python port of
  `zest-log2` / `zest-tick` / `zest-ticks` / `zest-bound` (Clarity int semantics:
  trunc-toward-zero division, floor for negatives) fuzzed against exact rational
  ground truth; deployed Zest source read from Hiro
  (`SP2NK9P261ZN3ZG2M1DS68PCJCRDFZVFMPYA6ZEST.clmm-pool-v1` @ height 9409214,
  `clmm-router-v1` @ 9409217, `SP1A27KFY4XERQCCRCARCYD1CC5N7M6688BSYADJ7.wstx`)
  and traced bin-by-bin (`route-x-iter` / `route-y-iter`, `step-x-for-y` /
  `step-y-for-x`, `accept`, `frame-price-limit`, `haircut`, `transfer-in` /
  `transfer-out` / `pay`, `get-fee-rates`); all 55 prior submissions read first
  and mapped (see §3). No fork run was executed for this review: the checks below
  are exact-arithmetic + source-traceable, and the poster's 107/107 stxer evidence
  is cited, not re-run.
- **Verdict:** **no High / Medium / fund-loss / limit-breach finding.** One new
  **Low** observation (O-1, §1): the tick-window construction misses the bound
  bin in a narrow regime and skips in-limit resting liquidity in a wider one.
  It never fills worse than `limit-price` and never strands funds, so it is a
  missed fill / possible min-out revert, not a price violation. Everything else
  in scope verified clean (§4).

Repro script: `verify_zest.py` (same folder as this report). Run:
`python3 verify_zest.py` — pure stdlib, fixed seeds, no network.

---

## 1. Finding O-1 (Low): the Zest tick window misses the bound bin at |tm-tb|=3, and skips in-limit resting liquidity at |tm-tb|>3

**Contract / function / lines:**
`swap-router-stx-usdcx-jing-v6.clar`, `zest-ticks` (L1210–1234) and
`zest-tick-step` (L1186–1208), called from `zest-stage` (L1281–1313), used by
`smart-swap-stx-for-usdcx` (L1352) and `smart-swap-usdcx-for-stx` (L1423).

**Root cause.** The walk is anchored only at `mid`: for a STX sale it starts at
`tm - 2` (`tm = zest-tick(mid-wad)`) and ascends to `tb + 1`
(`tb = zest-tick(bound)`); for a USDCx sale it starts at `tm + 2` and descends
to `tb - 1`. The bound tick itself is never an anchor. Zest has **no
active-tick pointer** — `route-x-iter` / `route-y-iter` in `clmm-pool-v1`
(L491–554) just iterate the supplied list and `step-x-for-y` /
`step-y-for-x` trade any bin holding the output token, capped per bin by the
`frame-price-limit` of the supplied bound. So a bin at tick `t <= tb` (sell
side) holding y-liquidity **can** fill at-or-better than the bound, wherever it
sits relative to `mid`. The window therefore has three exact regimes
(sell side; buy side symmetric, `tb - tm` instead of `tm - tb`):

| `tm - tb` | walk | consequence |
|---:|---|---|
| ≤ 2 | `[tm-2 … tb+1]`, covers `tb` | correct |
| **= 3** | **exactly `[tb+1]`** — one tick *past* the bound | **degenerate**: the tick's whole price range is above the bound, so the pool NOOPs it (`step-x-for-y` → `net = 0` → `NOOP`, L582–608); the bound bin `tb` itself, which could have partially filled up to the bound, is excluded. The stage still pays for a `get-fee-rates` read + a pool call and returns `ok: true, in = out = 0`. |
| ≥ 4 | empty → stage skipped (`ZEST_NONE`) | all in-limit resting liquidity at ticks `<= tb` below the window start is never read |

**Concrete scenario (sell side, honest `mid`).** Market mid = 1.00 USDCx/STX
(`mid = u100000000`), user limit = 1.03 (3% tighter than mid, e.g. a limit
order placed just above the market). Fee 30 bps. Then `bound = 967961165048543689`
WAD, `tm = zest-tick(1e18) = -1` (the known -1 edge bias), `tb = -4`, so
`tm - tb = 3`: the walk is exactly `[-3]` (`tb + 1`), one tick past the bound.
Bin `-4` (price range USDCx/STX ≈ 1.030–1.041, i.e. entirely at-or-better than
the 1.03 limit) is excluded. If bin `-4` holds USDCx, that fill is missed;
DLMM then prices the remainder at ~mid (1.00), which is *worse than the limit*,
so `dlmm-stage` plans 0 and the swap ends with `out` = Jing's fill only — and
reverts with `ERR_MIN_OUT` (u3002) if `min-usdcx-out` was set expecting the
Zest fill. A swap that could have filled (partially) at Zest inside the limit
instead reverts. (Numbers reproduced by `verify_zest.py`: limit 102% →
walk `[-3, -2]` covering `tb`; 103% → `[-3]` degenerate; 104% → `[]` empty.)

**Why it is only Low.** The fill never lands worse than `limit-price`: the
pool enforces the bound per bin (`frame-price-limit` rounds the max-price
*down* / min-price *up*, L743–758), DLMM enforces `limit-min`, and the
combined `min-out` is asserted on the balance-measured total. No funds move
except the tx fee, and no funds can strand (the router never uses
`as-contract`; §5). The loss is a missed fill and, in the narrow conjunction
(limit ~3 ticks tighter than mid **and** resting liquidity exactly at `tb`,
or a stale `mid` — see below), a min-out revert that a correct window would
have avoided. Impact is bounded by one bin's liquidity in regime `= 3`, and by
the venue spread in regime `>= 4`.

**Stale-`mid` threshold (regime `>= 4`).** With `mid` stale by `k` ticks in
the unfavorable direction (`tm = ta + k`, `ta` = true market tick), the walk
empties iff `k > (tb - ta) + 3`. So a tight limit (`tb ≈ ta`) dies on a
4-tick stale `mid`; a loose limit (`tb = ta + 20`) needs a 24-tick stale
`mid`. Verified by fuzz (Q5b). The headline claim still holds: a bad `mid`
fills less, never worse than `limit-price` — this finding is the *cost* of
that property, not a break of it.

**Suggested fix.** Anchor the walk start at the bound tick when it is the
worse side, as already proposed in substance by submission `mwi1ovns2a45011fd922`
(for the empty-window case only — see §2):
```clarity
tick: (if up (min (- tm ZEST_TICK_MARGIN) tb) (max (+ tm ZEST_TICK_MARGIN) tb))
```
With it, regime `= 3` becomes `[tb, tb+1]` (bound bin included) and regime
`>= 4` becomes `[tb, tb+1]` / `[tb-1, tb]` instead of empty. Note it is a
partial fix: resting liquidity *below* `tb` (sell side) is still outside the
32-tick window — a complete fix would need the FE to pass a `mid` near the
resting liquidity, which is the documented "mid picks the window" trade-off.

**How this differs from prior submission `mwi1ovns2a45011fd922` (#47).**
#47 claimed the stage "silently dies at ordinary limit prices" (limit 4% from
mid) as if that were incorrect behavior. With an honest `mid` and no resting
liquidity, an empty walk is *correct*: a limit >3 ticks tighter than the market
is not met by the market, so there is nothing to fill. #47's numbers
(`tm = -2` for `mid = 1.00`) are also off by one (`zest-tick(1e18) = -1`, the
known -1 edge bias). What #47 did **not** identify is (a) the `|tm-tb| = 3`
degenerate single-tick regime — the walk is non-empty yet useless and the
bound bin is excluded — and (b) the correct loss condition: the skip only
costs the user when in-limit resting liquidity exists outside the window
(or `mid` is stale). The fix direction coincides; the mechanism, the regime
split, and the impact analysis are new.

---

## 2. Refutations of prior claims (with proof — not re-claimed as findings)

**R-1 — Submission `mwjqe50m3c9ea5988e9b` (#52, "zest-log2 is broken by a scale
mismatch") is FALSE.** It asserts `ZEST_ONE = 2^64`. In fact
`ZEST_ONE = u1152921504606846976 = 2^60` and `ZEST_TWO = 2^61` (L1101–1104),
exactly matching the `2^60` fixed point of `ZEST_LOG2_WAD` /
`ZEST_LOG2_STEP`. Both constants are the *exact* integer floors (verified with
60-digit `Decimal`: diff 0 — the "diff 3720 / 15" in a float computation is
float error). The fold threshold `sq >= ZEST_TWO` fires normally, and the
fuzz in Q2 (20,982 valid `wad ≥ 1` cases: bin edges ±1 raw unit + log-uniform
randoms) gives tick deviation in `{0, -1}` only — never an over-estimate.
Consequently #52's corollary ("the Zest stage is ALWAYS a no-op") is also
false: it contradicts the poster's 107/107 stxer run and every fork run in
which Zest fills.

**R-2 — Submission `mwgevjh2eeb7b30d4e6d` Finding 2 ("split swaps miss the
`ERR_ZERO_LIMIT` assert; `limit-price = 0` aborts with division-by-zero in
`limit-min`") is FALSE.** The split entry points never pass the caller's
`limit-price` to `limit-min` / `dust-left`. The only `dust-left` call on the
split path is inside `fallback-residual` (L302–330), whose `limit` argument is
the *realized Jing price* `out·1e8/spent` (sell) or `spent·1e8/out` (buy),
guarded by `spent > 0` and `out > 0` — division by zero is impossible there.
The caller's `limit-price` reaches only `jing-swap` (the market contract, out
of scope). The buy-direction division `(/ (* base PRICE_SCALE) limit)` in
`limit-min` (L592) is reachable only via `dust-left` from `zest-stage` /
`dlmm-stage` / `cp-stage`, and both smart entries assert `(> limit-price u0)
ERR_ZERO_LIMIT` (L1340, L1411) before any of them run.

**R-3 — Submission `mwi1ovns2a45011fd922` (#47) framing is misleading** (see
§1): an empty walk at a limit ~4% tighter than an honest `mid` is correct
behavior, not a bug. The real loss condition is resting in-limit liquidity
outside the window (or a stale `mid`), and the distinct `|tm-tb| = 3`
degenerate regime is O-1.

**R-4 — The `zest-bound` L1243 `uint128` overflow (claimed by `mwb0ac1nd72924dc55af`
F-01, `mwb3aj2z8eb336ecfd0b` F-01, listed by `mwb3l1cv3d97371a1564`) is
UNREACHABLE — confirmed independently.** `zest-stage` runs `dust-left` first
(L1287); for the buy branch the stage proceeds only if
`limit-min(left, limit, false) = (left-2)·1e8/limit > 1`, and `limit-min`
itself aborts first if `(left-2)·1e8 ≥ 2^128`, so any `limit` reaching L1243
satisfies `limit < 2^128/2 = 170141183460469231731687303715884105728`, while the
overflow needs `limit ≥ 2^128 - 1e34 + 1 = 340272366920938463463374607431768211457`
— a factor-2 gap (Q6). A `UINT-MAX` limit makes `limit-min = 0` → dust →
`ZEST_NONE`; L1243 is never evaluated. (Confirms `mwb3kv09a6d37f2238c3`,
`mwbq9i779d47a9c9e3e0`.)

**R-5 — The `zest-bound` "rounds against the user" High
(`mwayu2iv42ed53374c25` F-1) is FALSE — confirmed independently.** Exact
reimplementation vs. the closed-form fee-adjusted bound over 20,000
`(limit, fee)` pairs × both directions: **0 violations**; the sell branch is
exactly `floor(1e26·(1-fee)/limit)` and the buy branch exactly
`ceil(1e26/(limit·(1-fee)))`, max gap to the exact bound 1.0000 WAD unit,
always in the user's favor (Q3). The proposed "ceil for sells of STX" fix
would *loosen* the x→y bound. (Confirms `mwaz7eay026a9dbc0c7c`, `mwb114r657ac087d6f18`,
`mwb3kv09a6d37f2238c3`, and others.)

---

## 3. Prior-art findings re-verified (not claimed — already submitted)

| # | Finding (first claimant) | My verification |
|---|---|---|
| 1 | `zest-tick` -1 bias at exact bin edges, absorbed by margin 2 (`mwaz7eay…` F-01) | Confirmed: ported `zest-log2(1e18)` is `ZEST_LOG2_WAD - 14659176100216` (2^-60 units); fuzz deviation ∈ {0,-1} only (Q2). Harmless. |
| 2 | Zest stage runs before DLMM and absorbs the order even when DLMM top-of-book is better (~0.068% on 5 USDCx; up to 0.59% in `mwdr30ge…` F1) (`mwazgoam…` L-01, `mwb3aj2z…` F-03, `mwdr30ge…` F1) | Confirmed by code reading: `zest-stage` is bounded only by `limit-price` (L1352/L1423), no DLMM-price comparison; `dlmm-pick` is only consulted by `dlmm-stage` afterwards. Real, already claimed. |
| 3 | Per-bin 1-raw-unit haircut (+ per-bin fee ceil) accumulates to ≤32 raw units below `limit-min`; header's "1-raw-unit output haircut" understates it (`mwb3aj2z…` F-02, `mwb7jz1b…` F-01, `mwff8jw…` F-01) | Confirmed against pool source: `haircut(z) = z - ((z>>40)+1)` (pool L830) — exactly 1 unit/bin for `out < 2^40`, plus `mul-div-up` fee ceil per bin in `accept` (L638–642) and `ceil-shift`/`l-error` padding. The header claim is wrong per-bin, but the combined `min-out` still guards the user; no fill can exceed the bound. |
| 4 | Split `leg-zest` has no dust guard: a 1-raw-unit (or empty-tick / >32-tick) Zest slice reverts the whole split via `u5001` (`mwb33cr1…` F-1, `mwbkrkek…` V-1, `mwexwnfn…`, `mwc9rg6r…` F1) | Confirmed: `allow-partial-fill = false` (L259/L268) + `try!` (L396/L510) + pool `(asserts! (or allow-partial-fill (is-eq left u0)) ERR-NOT-FILLED)` (pool L454/L480) + router remap `u2010 → u5001`. Liveness only (atomic revert, gas only). |
| 5 | Error-code collision: pool `u3004`–`u3007` pass through the router unmapped and collide with the router's own `ERR_SPLIT_MISMATCH` / `ERR_VAA_REQUIRED` / `ERR_ZERO_LIMIT` / `ERR_ZERO_MID` (`mwb0nok0…` F-1, `mwb33cr1…` F-2) | Confirmed: `router-error` (router-v1) remaps only `u2010/u2009/u2011/u2013` → `u5001`–`u5004`; `u3004` (tick out of range), `u3005`, `u3006`, `u3007`, `u1001` (paused) pass through raw. Diagnostics only. |
| 6 | Split `zest-route.price` is FE-supplied and never reconciled with `limit-price` (`mwb33cr1…` F-3, `mwfwzf13…`, `mwgevjh2…` F1, `mwc9rg6r…` O1) | Confirmed: `leg-zest` forwards `(get price route)` verbatim (L263/L273); `zest-bound` is only used by `zest-stage`. Backstops are `amm-mins.zest` (floored to u1) and the combined `min-out` — same trust model as the DLMM legs. |
| 7 | Deny-mode PC recipe: a complete v5-5 PC set aborts when Zest fills, and the documented `clmm-pool-v1 sends >= 1` recipe aborts on a Zest-0 fall-through (`mwb0nok0…` F-2, `mwdr30ge…` F3) | Confirmed by code reading (PCs are caller-side; the contract itself returns `ok` in both cases). Harness/documentation issue, not a contract bug. |
| 8 | `zest-ticks` in print/receipt counts ticks *provided*, not walked, including on error (`mwbq9i779…` Info) | Confirmed: `zest-swap` returns `ticks: (len ticks)` on success (L1261/L1272) and merges the same on error (L1265/L1276). Telemetry only. |
| 9 | Split `unsold` has no Zest-shortfall term; exact only because partial-fill is off (`mwhihzji…`, `mwhuemsb…`) | Confirmed: `unsold = residual-term + (dlmm-in - dlmm actual)` (L448–453/L562–567); exact given `leg-zest` is all-or-nothing. |
| 10 | `scale-min` / fallback `amm-mins.dlmm` unscaled when `dlmm = 0` + `fallback = (some u1)` (`mwbjwase…` F-01, `mwff8jw…` F-02) | **Out of scope for this diff**: `scale-min`, `with-fallback`, `fallback-residual` are byte-identical v5-5 → v6 (verified via `git diff --no-index`). The Zest leg does not touch the fallback path. Not claimed. |
| 11 | `limit-min` overflow for huge `left × limit` (sell) / huge `left` (buy) | **Pre-existing, out of scope**: `limit-min` / `dust-left` byte-identical v5-5 → v6; the first `dust-left` call and its operands are identical in both versions. Quantified in Q7 (sell: needs `(left-2)·limit ≥ 2^128`, e.g. `left = 1e15` needs `limit > 3.4e23`; buy: needs `left > 3.4e30`). Not reachable with real balances. |

Bogus prior claims (do not reproduce): `mwcek2i4…` F1 (u3004 sum omits zest —
the sum at L374–377/L488–491 *includes* zest) and `mwceki0n…` F1/F2 (Zest
runs before Jing / funds stranded — leg order is Jing → Zest, and Clarity tx
atomicity rolls the Jing leg back on any later abort; the router holds no
custody). Both refuted by `mwd0mpnqc0cc67e0787f` and by direct reading.

---

## 4. Verified clean (in-scope checks with line references)

- **Headline `mid` claim HOLDS.** `bound` derives only from `limit-price` +
  live `get-fee-rates` fee (`zest-stage` L1296–1303); `mid` enters only
  `mid-wad = 1e26/mid` (L1295) → `tm` (walk start). The pool enforces the bound
  per bin (`frame-price-limit`, pool L743–758, rounds max-price down /
  min-price up; `target = min/max(limit, b)` in `step-x-for-y` /
  `step-y-for-x`). A bad `mid` can only shrink/skip the walk (Q5 regimes),
  never push a fill past the bound. `mid = 0` is blocked by `ERR_ZERO_MID`
  (L1341/L1412); `mid > 1e26` gives `mid-wad = 0` → guarded skip (L1301).
- **`zest-bound` rounding** is conservative both ways (Q3, 0/20,000 violations)
  and is exactly the closed form (Q3); max intermediate `1e34 < 2^128`.
- **Tick math.** Constants exact (Decimal 60-digit, diff 0); `zest-log2` fold
  sound (`m ∈ [2^60, 2^61)`, `m² < 2^122`); `zest-tick` floors correctly for
  negatives (Q2: deviation ∈ {0,-1}, never over); walk monotone ±1, length
  ≤ 32, `unwrap-panic (as-max-len? … u32)` unreachable (32-step fold, ≤1 append
  per step); reachable walk ticks ⊆ `[-4168, 1863]` ⊂ `±4458`, so the clamp
  (L1176–1182) never activates on the smart path and the pool's
  `ERR-TICK-OUT-OF-RANGE` is unreachable from `zest-stage`.
- **No-fill never reverts (smart path).** Every `zest-stage` exit — dust
  (L1287), `get-fee-rates` err (L1310), `fee ≥ 1e8` → `bound = u0` (L1297),
  empty walk (L1305), any pool err incl. paused `u1001` (L1276/L1310) — degrades
  to `ZEST_NONE {in: 0, out: 0}` and the remainder flows to `dlmm-stage` /
  `cp-stage` on actuals (L1353–1354/L1424–1425). `zest-swap` uses
  `allow-partial-fill = true`, `min = 0` (L1257/L1268).
- **Native STX / custody.** No `as-contract` anywhere in v6; Zest `wstx`
  `transfer` is a bare `(stx-transfer? amount sender recipient)` (wstx L5–9);
  pool pulls with `sender = tx-sender` under `restrict-assets?` and pays out
  with `as-contract?` to `tx-sender` (pool L556–580), and `pay` asserts the
  recipient balance rose by exactly the transferred amount
  (`ERR-TRANSFER-MISMATCH` otherwise). Router holds 0 STX / 0 USDCx on every
  path; `dx`/`dy` returned equal exactly the amounts transferred.
- **Accounting.** Split `u3004` sum includes `zest` in both entries
  (L374–377, L488–491); leg order Jing → Zest → DLMM → XYK → Velar (execution
  order in the `let` bindings, L391–423/L505–537); `zest = u0` skips the call
  (L251); `fallback` stays DLMM-only (`valid-fallback` L340–344, `VENUE_ZEST`
  u4 never accepted as fallback); smart remainder chain
  `amount - jing - zest - dlmm - cp` with `unsold = (get unsold cp)` (L1352–1354,
  L1423–1425, `cp-stage` L1315–1329 stub returns `unsold: left`); `out` is
  balance-measured (`gain`, L102–108) and asserted vs the combined `min-out`
  (L411/L525/L1357/L1428). Receipt/print fields match the transfers
  (`zest-in`/`zest-out` after `jing-out`).
- **Fee.** `get-fee-rates(pool, tx-sender)` returns the *discounted* rates —
  same `discounted`/`discount-of` expression the swap path charges (pool
  L93–110 vs L444/L472) — and `zest-stage` picks `fee-rate-x` for x→y,
  `fee-rate-y` for y→x (L1291–1294), matching the pool. Pool fee cap
  `MAX-FEE-RATE = u10000000` (10%) makes `fee ≥ 1e8` impossible; the
  `(< fee ZEST_FEE_ONE)` guard is belt-and-braces.
- **Cost.** Bounded by construction: walk ≤ 32 ticks, `get-fee-rates` 1 read,
  fixed-length folds (`ZEST_WALK` 32, `ZEST_FRAC_BITS` 16). No path exceeds the
  poster's measured worst case (32 ticks + full DLMM walk ≈ 11% of block
  reads, `simulations/README-stxer.md` L34–44).

---

## 5. Reproducibility

- `python3 verify_zest.py` — exact-integer port + fuzz. Results:
  Q1 constants exact (`2^60`/`2^61`, `LOG2_WAD`/`LOG2_STEP` diff 0 at 60-digit
  precision; `zest-log2(1e18)` deficit `-14659176100216` = the -1 tick bias);
  Q2 tick deviation ∈ {0,1} over 20,982 valid cases, 0 over-estimates; Q3 bound
  0 violations / 20,000 pairs, max gap 1.0000 WAD; Q4 walk 0 violations /
  20,000 pairs, empty ⟺ `|tm-tb| > 3`; Q5 regimes 240,000 covered / 29,128
  degenerate / 90,872 empty, 0 violations; Q6 overflow unreachable (factor-2
  gap); Q8 haircut formula from pool source.
- Source verification: `git -C jing-contracts-v3 rev-parse HEAD` →
  `9dab9bd…`; `sha256sum contracts/stx-usdcx/swap-router-stx-usdcx-jing-v6.clar`
  → `d974ea91…`; pool/router/wstx source fetched from
  `api.hiro.so/v2/contracts/source/…` (files under `zest-src/`).
- Not run: the stxer mainnet-fork harness (cited 107/107 evidence) and any
  mainnet transaction. No wallet was unlocked, no transaction signed, nothing
  submitted — per the task constraints.

---

## 6. Submission draft (DO NOT SUBMIT — needs Mas's approval; content_url must be a public link to this report first)

**Message (≤ 2000 chars, 1,223 chars):**

```
Audit v6 Zest CLMM (9dab9bd, sha d974ea91=pin), diff vs v5-5 only, all 55 prior submissions read. 1 new Low + refutations; no High/Medium, no fund loss, no limit breach.

O-1 LOW — zest-ticks (L1210-1234): walk anchored only at mid misses the bound bin. |tm-tb|=3 gives a 1-tick walk [tb+1] past the bound (pool NOOPs it) while bin tb, which could partially fill up to the bound, is excluded; |tm-tb|>3 empties the walk, skipping in-limit resting liquidity below the window. Never worse than limit-price (pool enforces bound/DLMM+min-out guard); loss is a missed fill / possible min-out revert. Fix: anchor start at min(tm-2,tb)/max(tm+2,tb). Distinct from #47: #47's "ordinary limits" framing is wrong (empty walk is correct absent resting liquidity); the |tm-tb|=3 degenerate regime is new.

Refuted with proof: #52 log2 "scale mismatch" (ZEST_ONE=2^60, constants exact, 0 over-estimates in 20,982 cases); mwgevjh2 F2 zero-limit div-by-zero (split path never passes caller limit to limit-min); L1243 overflow unreachable (dust gate caps limit <2^128/2 vs need 3.4e38); mwayu2iv F1 rounding (0/20k violations, bound is exact closed form).

Full report + reproducible exact-arithmetic checks (verify_zest.py): <content_url>
```

**content_url:** `TODO — host this report publicly first (e.g. gist) and paste the URL here. Local file: ~/workspace/aibtc/audit-zest-v6.md`

**Payout (if awarded):** per the registered agent — BTC `bc1q3dwewy7zdu2zwt4d5p8r6un9mvx9835gmu6784`, STX `SP3NEJSB9Y3BZPH2YCQKWRAGK7ZA2P2ZC3WNZZG9Q` ("Atomic Sprite").
