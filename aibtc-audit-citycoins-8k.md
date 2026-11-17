# Audit: CityCoins CCIP-028 activation + ccd015 MIA burn book + ccd016 sBTC→STX vault (pre-deploy)

- **Target:** `github.com/Rapha-btc/citycoins-protocol`, branch
  `review/ccip028-direct-activation`, HEAD `0803819`
  (`citycoins/protocol` PR #92).
- **Pins verified (sha256):**
  - `contracts/extensions/ccd015-redemption-book-mia-stx.clar` —
    `b3526d4c…` ✓ matches the bounty pin.
  - `contracts/extensions/ccd016-swap-vault-mia-v2.clar` — HEAD is
    `00f06f0c…`, **not** the bounty pin `ac0c305f…`. `git diff` pin→HEAD
    is 22 lines, all of it the Jing rebind (`markets-sbtc-stx-jing-v6-4` →
    `v6-5`, `swap-router-sbtc-stx-jing-v5-5` → `v5-6`) plus one comment.
    No logic changed. This review covers HEAD and therefore the pinned
    version too; §1 verifies the rebind live against mainnet.
  - `contracts/proposals/ccip028-activate-mia-fair-redemption.clar` —
    `8826bc5d…` ✓ matches the hash cited in prior submissions.
- **Bounty:** AIBTC `mw4761qx68024266725f`, "Audit 8k: CityCoins CCIP-028
  activation + ccd015 MIA burn book + ccd016 sBTC->STX vault (pre-deploy)",
  deadline 19 Nov 2026 23:59 UTC.
- **Method:** full line-by-line read of all three contracts (50 + 510 +
  1141 lines); all 63 prior submissions read first and mapped (see §3);
  exact-integer Python checks of the book/vault arithmetic
  (`verify_citycoins.py`, same folder as this report — pure stdlib, fixed
  seeds, no network); live mainnet ABI verification of the rebound Jing
  market/router via Hiro; the repo's own activation suite re-run on HEAD
  (8/8 pass, see §2).
- **Verdict: no new paid-eligible finding.** No High / Medium, no fund
  loss, no path where a user is filled worse than a stated bound, no
  stuck funds beyond the already-known items in §3 (which I verified and
  deliberately do NOT re-claim). One Info note (§4): the HEAD rebind is
  interface-compatible, verified live — recorded here so the pin/HEAD
  drift is not mistaken for an unreviewed change.

Repro: `python3 verify_citycoins.py` — 0 fails. Activation suite:
`npm run test:ccip028` — 8/8 pass (run 2026-11-17 on HEAD `0803819`).

---

## 1. The HEAD rebind (v6-4→v6-5, v5-5→v5-6) is interface-compatible — verified live

The only diff between the bounty-pinned ccd016 and HEAD is the Jing
binding. I checked every function the vault calls against the live
mainnet ABIs (Hiro `/v2/contracts/interface`):

| Contract | Function the vault calls | Live? | Signature matches vault call? |
|---|---|---|---|
| market v6-5 | `get-current-cycle` (read-only) | yes | `() -> uint` |
| market v6-5 | `get-token-x-deposit` (read-only) | yes | `(cycle, depositor) -> uint` |
| market v6-5 | `get-token-x-parked` (read-only) | yes | `(who) -> uint` |
| market v6-5 | `get-token-x-pending-deposit` (read-only) | yes | `(depositor) -> (optional {amount, limit, spread-bps, submitted-at})` |
| market v6-5 | `deposit-token-x` | yes | `(amount, limit-price, spread-bps?, trait, asset-name)` |
| market v6-5 | `set-token-x-limit` | yes | `(limit-price, spread-bps?)` |
| market v6-5 | `swap` | yes | `(amount, limit-price, update, tx-trait, tx-name, ty-trait, ty-name, deposit-x)` → `(response {rebate-refunded, token-x-received, token-x-rolled, token-y-received, token-y-rolled})` |
| market v6-5 | `cancel-token-x-deposit` | yes | `(trait, asset-name)` |
| market v6-5 | `refresh-mid` | yes | `(update) -> (response uint uint)` |
| market v6-5 | `get-min-deposits` (read-only) | yes | `() -> {min-token-x, min-token-y}` |
| router v5-6 | `smart-swap-sbtc-for-stx` | yes | `(amount, limit-price, update?, mid, min-stx-out)` → `(response {…, out, unsold, …})` |
| router v5-6 | `swap-sbtc-for-stx` | yes | `(amount, jing-amount, limit-price, update?, fallback?, amm-amounts, amm-mins, min-stx-out)` → `(response {…, out, unsold, …})` |

The vault reads `token-y-received` from the market swap and `out` /
`unsold` from the router — all present with the expected types. The
rebind changes no behavior the vault depends on.

## 2. What was verified clean (with evidence)

- **CCIP-028 auth (L13-15):** `contract-caller = DAO AND tx-sender = DAO`.
  A direct call (even from the deployer or an approver) cannot initialize
  anything; only `base-dao.execute` calls proposals as-contract. Re-init
  is blocked twice: base-dao's `ExecutedProposals` map (u901 on re-run)
  and the `get-par-scaled == u0` guard (sound because `update-par`
  asserts `snapshot > 0` before writing par). Confirmed by the repo's own
  activation suite, re-run here: 8/8 pass, including the stranger /
  deployer / approver negative controls, the duplicate-approver case, the
  sunset case, and the failed-par full-rollback case.
- **CCIP-028 atomicity:** all 13 sub-calls use `try!` inside one `begin`;
  a failed `update-par` (empty treasury / zero supply) rolls back the
  extension grant, the allowlist entry, all 9 param sets and the proposal
  execution itself — so activation is fully re-runnable. (The revert
  itself, when backing is zero, is the already-claimed par-dependency
  Medium in §3; I do not re-claim it.)
- **CCIP-028 params:** all 9 vault values within their `MAX_*` caps
  (checked in `verify_citycoins.py` §7); `leeway u1000` sits exactly at
  its cap, which is valid. `set-min-deposit u100000000000` =
  100,000 MIA × 1e6 micro-units ✓. `set-paused false` and the
  min-deposit set are no-ops against the book's defaults — harmless.
- **Par formula (ccd015 L337-388):** `treasury-ustx * 1e8 / supply`,
  treasury = mining-v3 locked+unlocked + pox5-staking locked+unlocked via
  `stx-account` (stacked STX is counted, correctly — it is backing that
  unlocks); supply = v1×1e6 + v2. `calculate-par` returns `none` (→
  `ERR_PAR_CALCULATION`) exactly when treasury or supply is zero; the
  truncation-to-zero at thin backing is the already-claimed F2 in §3.
  `update-par` computes the snapshot *before* the DAO/extension auth
  check, but `calculate-par` is read-only — no state changes before auth.
- **Book ordering & settlement (ccd015):** `insert-step` keeps the book
  sorted ascending by `ustx/amount` via cross-multiplication; worst-case
  products are ≤ 1e28 < 2^128 (§3 of the script). `settle-step` partial
  fill verified over 200,000 random cases: the leftover record's implied
  price is always ≤ the original price, and the seller is always paid at
  or better than their ask (§1 of the script). `at-or-below-par?` is a
  direct cross-multiplied comparison, no truncating division; worst-case
  products ≤ 1e25 (§2). `cross-book` spends only the contract's own STX
  (budget = balance, hard-capped by the `with-stx` allowance), burns
  exactly what it acquires, and reverts (`ERR_NO_FILL`) if nothing fills.
  `place-offer` / `change-offer` / `cancel-offer` paths traced; the
  full-book eviction requires a strictly better price and refunds the
  evicted seller before inserting.
- **Vault clock (ccd016):** the window opens only from an empty vault (or
  no clock, or an elapsed window with ≤ 8 sats left over) — the 1-sat
  re-arming hole from the earlier cut is closed. `fund-from-treasury`
  pulls the whole treasury balance (by design — the batch is the whole
  balance) and joins an elapsed batch without re-arming it. `close-batch`
  and `close-if-empty` clear the clock exactly when the vault is empty.
- **Vault exits:** STX leaves only to the ccd015 book (`fuel-fair-book`,
  less the `pyth-fee-budget` reserve); sBTC leaves only to the rewards
  treasury (`dao-recall-sbtc`, DAO-gated). `dao-recall-sbtc` needs a prior
  `dao-reclaim` for resting Jing deposits — documented in the code.
- **Vault floors (ccd016):** `router-swap` sells at `floor-of(mid)` =
  mid × (1 − slippage) with a post-swap check `out >=
  floor-out(sold − 8, limit)` that reverts the whole tx if violated (the
  `sold > 8` assert precedes the subtraction, so no underflow).
  `router-swap-split` passes per-venue mins from the same oracle floor
  (Velar at the 60 bps floor, twice its 30 bps fee). `jing-take` is
  DAO-only and documented as having no chunk cap; `sweep-amount` only
  sweeps the whole balance when it fits in one chunk. The 1-block router
  cooldown is shared by both router entries and stamps before the swap,
  so a failed swap does not burn the cooldown.
- **Oracle arithmetic:** DIA band products (`mid × 10000`, `dia × (10000
  ± band)`), `floor-out` products, and `get-dia-price` products are all
  ≤ 1e24 < 2^128 (§4–6 of the script) at live magnitudes and at 1000×
  stress values. `get-dia-value` rejects zero values and stale (> 2 h)
  pushes; on DIA error the native-RFQ fallback halves the mid as the
  limit — the dial-ignoring aspect of that branch is the already-claimed
  H2/HIGH in §3.

## 3. Already claimed by others — verified, NOT re-claimed

I read all 63 prior submissions. These are real, already-reported items;
I verified each holds as described and I claim none of them:

- **apeir L-1:** after a `dao-recall-sbtc`, a stranger's permissionless
  `fund-from-treasury` pulls the treasury's whole sBTC balance back and
  opens a new window (the recall's `close-if-empty` clears the clock).
- **apeir L-2:** `cross-book` is the only STX exit from the book; STX
  pushed in by the vault is stuck if MIA stays above par / the programme
  ends (no DAO recall for STX).
- **Par-dependency Medium:** `execute` hard-depends on non-zero par —
  `update-par` asserts `snapshot > 0`, so activation reverts atomically
  when the treasury is empty or supply is zero, contradicting the "no
  reward balance required" comment.
- **Partial-fill dust-trap Medium:** a partially filled seller whose
  remainder drops below `min-deposit` cannot reprice via `change-offer`
  (the min-deposit assert applies even to reprice-only calls).
- **Pyth-fee-budget-0 bricking:** with `pyth-fee-budget = 0` and a
  non-zero Lazer fee, every oracle-dependent entry reverts and the vault
  has no on-chain path to collect STX fees until a manual donation +
  budget proposal.
- **DIA-fallback dial (H2 / HIGH claim):** on DIA error,
  `get-no-pyth-price` uses `limit = mid / 2` and never reads
  `no-pyth-slippage-bps`, so the DAO's configured emergency tolerance is
  silently bypassed; the DIA emergency split also reuses one 10% limit
  for all legs including Velar.
- **`set-min-deposit` has no upper bound (Low, with Clarinet repro):** a
  DAO can set it above `MAX_PER_TRANSACTION` and stop new offers (the
  same submission shows it is reversible by the DAO and sellers can still
  cancel).
- **Same-address deploy footgun:** the vault's `STX_FAIR_BOOK` binds to
  the book at the vault's own deployer, so book and vault must ship from
  the same address, book first.
- **README 1b (prior paid audit, accepted, no change):** a DIA outage /
  stale push makes `current-mid` fail; the remedy is the
  `set-dia-band-bps 0` proposal. My own first candidate (a >10% BTC move
  vs a stale DIA push diverging the band) is a variant of this known
  item, so I do not claim it.

## 4. Info note (not a finding): pin/HEAD drift

The branch HEAD (`0803819`) moved ccd016 off the bounty pin (`ac0c305f`)
by rebinding the Jing market/router. The diff is binding-only and §1
verifies the new bindings live. If the poster judges against the pin,
nothing in this review depends on the rebind; if against HEAD, the
rebind is verified compatible. Either way the verdict is unchanged.

---

## Submission summary (≤ 2000 chars is in the message, not here)

No new paid-eligible finding. Rigorous no-findings review: 3 contracts
read line-by-line, all 63 prior submissions mapped, exact-arithmetic
checks (200k-case fuzz of the book's partial-fill invariant + overflow
bounds + param caps) all pass, live mainnet ABI verification of the
rebound Jing market v6-5 / router v5-6, and the repo's activation suite
re-run 8/8 on HEAD. Payout: `bc1q3dwewy7zdu2zwt4d5p8r6un9mvx9835gmu6784`
(Atomic Sprite).
