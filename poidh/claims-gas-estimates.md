# POIDH claims — gas estimates (17 Nov 2026, ~11:35 WIB)

Wallet: 0x6D01a7E68634Bc6A685c83Fc44bEB6D9b21d4a0D (saldo 0 ETH — klaim TIDAK dikirim)
Kontrak v3 Base: 0x5555fa783936c260f77385b4e153b9725fef1719 (chainId 8453)
Gas price live via mainnet.base.org eth_gasPrice: 0x5b8d80 = 6,000,000 wei = 0.006 gwei
ETH ~$1.815 (dicek 17 Nov ~10:01 WIB)

## ⚠️ KOREKSI PENTING (17 Nov ~11:35 WIB) — analisis gas sebelumnya SALAH 1000x

Estimasi gas SEBELUMNYA (claims-gas-estimates.md v1, ~11:20 WIB) menulis biaya
"0.00791 ETH (~$14.36)" untuk introstats dan "0.00819 ETH (~$14.86)" untuk
saltorious. Itu SALAH hitung 1000x.

Hitungan yang benar: 1,318,351 gas × 6,000,000 wei = 7.91×10¹² wei = 0.00000791 ETH
(~$0.014), BUKAN 0.00791 ETH. (1 ETH = 10¹⁸ wei; 7.91×10¹² / 10¹⁸ = 7.91×10⁻⁶.)

Gas price 0.006 gwei TERKONFIRMASI live via eth_gasPrice (0x5b8d80) dan
eth_estimateGas untuk klaim FAO (1,341,661 gas) pada 17 Nov ~11:35 WIB.

**Dampak koreksi — SEMUA kesimpulan gas sebelumnya TERBALIK:**
- Saltorious: gas ~$0.009–0.015 vs hadiah $5.98 → SANGAT MENGUNTUNGKAN bila menang
  (sebelumnya diklaim "rugi pasti" — SALAH).
- Introstats: gas ~$0.014 vs hadiah $14.50 → SANGAT MENGUNTUNGKAN bila menang
  (sebelumnya diklaim "impas" — SALAH).
- FAO 1531: gas ~$0.015 vs hadiah $907.50 (0.5 ETH) / $4,907.50 (0.5 ETH + 4,000 USDC)
  → gas = 0.002% dari hadiah.
- 0.001 ETH (~$1.82) cukup untuk ~100x klaim POIDH pada gas price ini.
- Catatan: gas price bisa naik saat jaringan sibuk; cek ulang sebelum kirim.
  Walau naik 100x (0.6 gwei), biaya klaim tetap ~$1.50 — masih jauh di bawah hadiah.

## 1. Saltorious — bounty 1551 (0.0033 ETH ~ $5.98)
- Deskripsi PENUH (~1.400 karakter): gas 1.364.672 → 0.00000819 ETH (~$0.015)
- Deskripsi PENDEK (~450 karakter): gas 786.085 → 0.00000472 ETH (~$0.009)
- signUrl: https://poidh.xyz/tx?action=submit_claim&chain=base&id=1551 (lengkap di claim-saltorious-prepared.json)
- KESIMPULAN (dikoreksi): gas JAUH LEBIH KECIL dari hadiahnya. Klaim MENGUNTUNGKAN bila menang.

## 2. Intro Statistics — bounty 1554 (0.008 ETH ~ $14.50)
- Deskripsi PENUH (~1.500 karakter): gas 1.318.351 → 0.00000791 ETH (~$0.014)
- Deskripsi PENDEK (perkiraan): ~0.0000047 ETH (~$0.009)
- signUrl: https://poidh.xyz/tx?action=submit_claim&chain=base&id=1554 (lengkap di claim-introstats-prepared.json)
- KESIMPULAN (dikoreksi): gas JAUH LEBIH KECIL dari hadiahnya. Klaim MENGUNTUNGKAN bila menang.

## 3. FAO Operating Plan — bounty 1531 (0.5 ETH + 4,000 USDC ~ $4,907.50)
- Deskripsi (~1.100 karakter): gas 1,341,661 (eth_estimateGas live) → 0.00000805 ETH (~$0.015)
- Dengan buffer +20%: 1,609,993 gas → 0.00000966 ETH (~$0.018)
- signUrl: https://poidh.xyz/tx?action=submit_claim&chain=base&id=1531 (lengkap di claim-fao1531-prepared.json)
- Plan: https://raw.githubusercontent.com/DjavaProductions/swarm-triage/main/poidh/fao-plan/foreguild-operating-plan.html
- Model: https://raw.githubusercontent.com/DjavaProductions/swarm-triage/main/poidh/fao-plan/foreguild-financial-model.csv
- KESIMPULAN: gas 0.002% dari hadiah. Klaim SANGAT LAYAK dikirim.
- PERINGATAN DEADLINE: teks bounty menyebut submissions tutup 12 Nov 23:59 AoE,
  tapi API live masih in_progress + acceptingClaims true per 17 Nov. Klaim bisa
  saja ditolak karena deadline — kirim secepatnya, jangan ditunda.

## Catatan
- Gas didominasi penyimpanan on-chain (3 string: title, description, proofUri).
  Biaya dasar createClaim ~786k gas walau deskripsi pendek.
- Untuk mengirim klaim: buka signUrl di browser dengan wallet Base berisi ≥0.001 ETH
  (sudah lebih dari cukup untuk puluhan klaim), atau kirim tx mentah dari
  claim-*-prepared.json (field transaction).
- Wallet Base: 0x6D01a7E68634Bc6A685c83Fc44bEB6D9b21d4a0D (saldo 0 — perlu diisi dulu).
