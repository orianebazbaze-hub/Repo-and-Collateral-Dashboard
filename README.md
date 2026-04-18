# Collateral Management Dashboard

> **Corporate Treasury | Repo & Collateral Management**  
> Real-time collateral tracking, margin computation and stress testing for a repo desk.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![JavaScript](https://img.shields.io/badge/JavaScript-ES2022-yellow)

> **Fictitious portfolio for demonstration purposes only.** All positions (OAT, Bund, BTP, KfW, CADES, CRH Cover, LVMH, Total), notionals, repo rates and market parameters are simulated. Not for trading.
<img width="710" height="515" alt="Capture d’écran 2026-04-17 à 13 11 00" src="https://github.com/user-attachments/assets/ef18cee7-c324-483e-99a9-84ea2a4f3987" />
<img width="715" height="312" alt="Capture d’écran 2026-04-17 à 13 11 32" src="https://github.com/user-attachments/assets/c9922763-4b4d-4f04-bbd8-5d4e08dd6eea" />
<img width="714" height="610" alt="Capture d’écran 2026-04-17 à 13 11 48" src="https://github.com/user-attachments/assets/c6469bfb-4839-4ad5-884a-afc8baaccf9c" />
<img width="715" height="662" alt="Capture d’écran 2026-04-17 à 13 13 06" src="https://github.com/user-attachments/assets/6082fd74-f88c-4334-be20-0a0e34f2fbe0" />

---

## Use Case

A **Corporate Treasury repo desk** manages ~€206M collateral pool across 8 instruments and 6 repo counterparties, and needs to:

Track **collateral pool** in real-time (sovereigns, agencies, covered bonds, corporates)  
Apply **haircuts** per ICMA/ECB framework (by asset class × rating × maturity)  
Monitor **HQLA tiers** (L1 / L2A / L2B) and ECB eligibility  
Compute **Initial Margin** (SIMM-inspired) and **Variation Margin** per repo  
Trigger **margin calls** with threshold, MTA, rounding per CSA/GMRA terms  
Run **stress scenarios** (parallel rate shifts −200bp to +200bp)

This dashboard delivers all of that **in one interface**.

---

## Architecture

```
┌──────────────────────────────────┐
│  Flask Backend (Python 3.10+)    │
├──────────────────────────────────┤
│ • OIS curve bootstrap            │
│ • Bond pricing & duration        │
│ • Haircut matrix (ICMA/ECB)      │
│ • IM (SIMM-based) & VM           │
│ • Margin call triggers           │
│ • Stress scenarios               │
└──────────────────────────────────┘
              ↕
         REST API (5 routes)
              ↕
┌──────────────────────────────────┐
│ JavaScript Frontend (HTML/CSS)   │
├──────────────────────────────────┤
│ • 6 interactive views            │
│ • Colour-coded haircut matrix    │
│ • Margin call cards + alerts     │
│ • Stress scenario builder        │
│ • Dark theme, responsive         │
└──────────────────────────────────┘
```

---

## Instruments

| Type | Example | Notional | Haircut | HQLA Tier | ECB Eligible |
|---|---|---|---|---|---|
| **Sovereign** | OAT 3% 2034 | €50M | 2.5% | L1 | Yes |
| **Sovereign** | Bund 2.5% 2029 | €40M | 1.5% | L1 | Yes |
| **Sovereign** | BTP 4% 2031 | €30M | 3.0% | L1 | Yes |
| **Agency** | KfW 2.75% 2030 | €25M | 2.5% | L2A | Yes |
| **Agency** | CADES 3% 2033 | €20M | 3.5% | L2A | Yes |
| **Covered Bond** | CRH Cover 3.5% 2028 | €15M | 2.0% | L2A | Yes |
| **Corporate** | LVMH 2% 2027 | €10M | 3.0% | L2B | No |
| **Corporate** | Total 3.125% 2032 | €12M | 7.5% | L2B | No |

---

## Dashboard Views

### 1. **Overview**
Pool MV, CV post-haircut, donut by asset class, HQLA tiers, repo summary table.

### 2. **Collateral Pool**
Full bond inventory with live pricing, haircuts, HQLA tier, ECB eligibility, modified duration.

### 3. **Haircut Matrix**
Colour-coded grid by asset class × rating × maturity bucket. Implements ICMA GMRA / ECB collateral framework logic.

### 4. **Repo Positions**
Active book of 6 repo positions:
- Haircut applied to collateral per ICMA/ECB framework
- Initial Margin (IM) — `IM = Haircut × Notional`
- Variation Margin (VM) — `collateral value after haircut − repo notional`
- Threshold, MTA (Minimum Transfer Amount), rounding per CSA/GMRA
- Triparty agents (Euroclear, Clearstream) tracked separately from counterparties

### 5. **Margin Calls**
Per-counterparty status: OK / MONITOR (>70% threshold) / CALL triggered. Call amount after threshold + MTA + rounding.

### 6. **Stress Scenarios**
Interactive slider ±200bp parallel shift applied to all collateral:
- Per-repo impact on MV and CV
- New margin calls triggered
- Sensitivity curve: #calls and CV change vs rate shift

---

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python app.py

# Open browser
# → http://localhost:5001
```

Dashboard loads with **8 collateral instruments** (€206M) and **6 repo positions**.

---

## API Reference

| Endpoint | Description |
|---|---|
| `GET /api/pool` | Collateral pool with pricing, haircuts, CV |
| `GET /api/repo` | Repo book with IM, VM, margin call status |
| `GET /api/haircuts` | Full haircut matrix |
| `GET /api/margin_calls` | Per-counterparty margin call detail |
| `GET /api/stress?shift=N` | Stress scenario at N basis points |

---

## Key Metrics Explained

### Collateral Metrics

**Market Value (MV)**
- Live price × notional for each bond
- Discounted via OIS curve for realistic pricing

**Collateral Value (CV)**
- `CV = MV × (1 − haircut)`
- Haircut per ICMA/ECB framework

**Haircuts**
- **Sovereign L1**: 1.5%–3.0% (based on rating, maturity)
- **Agency L2A**: 2.5%–3.5%
- **Covered L2A**: 2.0%
- **Corporate L2B**: 3.0%–7.5% (highest, reflects liquidity risk)

### Margin Metrics

**Initial Margin (IM)** — :
```
`IM = Haircut × Notional`
```


**Variation Margin (VM)**
```
VM = Collateral Value (post-haircut) − Repo Notional
```
- Positive VM = over-collateralised (OK)
- Negative VM = under-collateralised (call triggered if |VM| > threshold + MTA)

**Call Logic**
1. Compute VM per repo
2. Check: `|VM − Threshold| > MTA`?
3. If yes: round to nearest multiple of rounding (e.g., €100K)
4. Call amount delivered

### Stress Metrics

**Rate Shift Impact**
- +100bp rates → bonds lose value → CV drops → new margin calls
- −100bp rates → bonds gain value → over-collateralised → partial releases

---

## Technical Stack

**Backend:** Python 3.10+ + Flask + NumPy + SciPy  
**Frontend:** Vanilla JavaScript + Chart.js (donuts, bar charts)  
**Pricing:** OIS curve (cubic spline), bond duration  
**Performance:** All calculations < 100ms  

---

## Files

```
collateral_dashboard/
├── app.py                  # Flask backend
├── templates/
│   └── index.html          # Frontend (dark theme)
├── requirements.txt        # Dependencies
└── README.md              # This file
```

---

## Regulatory References

- **ICMA GMRA** — Global Master Repo Agreement
- **ECB Collateral Framework** — Guideline ECB/2014/60
- **BCBS/IOSCO Margin Requirements** — for non-centrally cleared derivatives
- **ISDA SIMM** — Standard Initial Margin Model

---

## Limitations & Notes

 **Portfolio is fictitious** — rates, notionals, haircuts are simulated  
 **Simplified IM model** — real SIMM is multi-factor (delta, vega, curvature, base corr)  
 **Parallel shifts only** — real stress uses key rate durations, non-parallel twists  
 **No real-time market data feeds** — all rates hard-coded (for demo)  

---

## Next Steps

- **Connect to live market data** (Bloomberg, Reuters, ECB APIs)
- **Full SIMM implementation** (ISDA CRIF format support)
- **CSA-based collateral optimisation** (cheapest-to-deliver logic)
- **Triparty messaging** (Euroclear CmaX, Clearstream Xemac)
- 
## Author
ob
