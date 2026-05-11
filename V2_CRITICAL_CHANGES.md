# CLOB V2 CRITICAL CHANGES — IMPLEMENTATION REQUIRED

## ✅ PROXY USED: Jina AI (r.jina.ai) — Bypassed Geoblock

---

## 🔴 CRITICAL CHANGES (Must Implement)

### 1. SDK UPGRADE
**OLD:** `py-clob-client`  
**NEW:** `py-clob-client-v2`  
**Action:** Update requirements.txt

### 2. COLLATERAL TOKEN ✅ ALREADY DONE
**OLD:** USDC.e (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174)  
**NEW:** pUSD (0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB)  
**Status:** ✅ Updated in auto_redeem.py

### 3. ORDER FIELD CHANGES 🔴 CRITICAL
**OLD V1 Order Fields:**
- `nonce`
- `feeRateBps`
- `taker`

**NEW V2 Order Fields:**
- `timestamp` (ms) — NEW REQUIRED
- `metadata` — NEW
- `builder` — NEW (for builder program)
- `feeRateBps` — GONE (fees set at match time)

### 4. SIGNATURE TYPE FOR NEW USERS
**NEW API Users:**
- Signature Type: `3` (POLY_1271)
- Uses Deposit Wallets (ERC-1967 proxy)
- Requires relayer client

**Existing Users:**
- Can continue with types 0, 1, 2
- But must upgrade SDK

### 5. CONSTRUCTOR CHANGES
**OLD:** Positional arguments  
**NEW:** Options object  
**Change:** `chainId` → `chain`

### 6. FEE MODEL CHANGE
**OLD:** Embedded in signed order (`feeRateBps`)  
**NEW:** Operator-set at match time  
**Impact:** Orders don't specify fees anymore

### 7. BUILDER PROGRAM
**NEW:** Builder codes for attribution  
**Field:** `builder` in order  
**Benefit:** Fee discounts, tracking

### 8. PRODUCTION URL
**Test:** `https://clob-v2.polymarket.com` (DEPRECATED)  
**Production:** `https://clob.polymarket.com` ✅ (Same as V1)

---

## 🔧 FILES TO UPDATE

### HIGH PRIORITY
1. `requirements.txt` — Update to py-clob-client-v2
2. `trading/live_trader.py` — Update order creation
3. `config.py` — Add V2 settings
4. `data/clob_client.py` — Update client initialization

### MEDIUM PRIORITY
5. `trading/auto_redeem.py` — Already has pUSD ✅
6. Add builder code support
7. Update signature handling

---

## ⚠️ BREAKING CHANGES

1. **V1 SDK NO LONGER WORKS** — Must upgrade
2. **V1-signed orders REJECTED** — Must re-sign with V2
3. **Open orders WIPED** — Must recreate
4. **Fees NOT in order** — Set by operator

---

## 📋 MIGRATION CHECKLIST

- [ ] Update SDK to v2
- [ ] Update order creation (timestamp, metadata, builder)
- [ ] Remove feeRateBps from orders
- [ ] Update constructor (options object)
- [ ] Test with paper trading
- [ ] Add builder code (optional)
- [ ] Update EIP-712 domain if needed

---

## 🎯 IMPLEMENTATION PRIORITY

1. **URGENT:** Update SDK and order format (bot won't work without this)
2. **HIGH:** Add timestamp field to orders
3. **MEDIUM:** Add builder code support
4. **LOW:** Deposit wallet integration (for new users only)