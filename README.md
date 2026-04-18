
# Collateral Management Dashboard

> **Repo & Collateral Management**  
> Full-stack collateral management system: Python risk engine (Flask REST API) + JavaScript frontend.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![JavaScript](https="img.shields.io/badge/JavaScript-ES2022-yellow")

> **Fictitious portfolio for demonstration purposes only.** Instruments (OAT, Bund, BTP, KfW, CADES, LVMH, Total), notionals, repo rates and market parameters are simulated. The purpose is to demonstrate collateral management, margin computation and stress testing capabilities.

<img width="710" height="515" alt="Capture d’écran 2026-04-17 à 13 11 00" src="https://github.com/user-attachments/assets/ef18cee7-c324-483e-99a9-84ea2a4f3987" />
<img width="715" height="312" alt="Capture d’écran 2026-04-17 à 13 11 32" src="https://github.com/user-attachments/assets/c9922763-4b4d-4f04-bbd8-5d4e08dd6eea" />
<img width="714" height="610" alt="Capture d’écran 2026-04-17 à 13 11 48" src="https://github.com/user-attachments/assets/c6469bfb-4839-4ad5-884a-afc8baaccf9c" />
<img width="715" height="662" alt="Capture d’écran 2026-04-17 à 13 13 06" src="https://github.com/user-attachments/assets/6082fd74-f88c-4334-be20-0a0e34f2fbe0" />


---

## Overview

```
┌──────────────────────────┐    REST API    ┌────────────────────────────────────┐
│  Python Risk Engine      │ ◄─────────────│  JavaScript Dashboard              │
│                          │               │                                    │
│ • Bond pricing (OIS)     │ /api/pool     │ • Collateral pool overview         │
│ • Haircut matrix         │ /api/repo     │ • Haircut matrix (colour-coded)    │
│ • VM / IM computation    │ /api/haircuts │ • Repo book with IM / VM           │
│ • Margin call triggers   │ /api/margins  │ • Margin call cards + alerts       │
│ • Stress scenarios       │ /api/stress   │ • Stress scenario builder          │
└──────────────────────────┘               └────────────────────────────────────┘
```

## Quickstart

```bash
pip install -r requirements.txt
python app.py
# open http://localhost:5001
```

## Dashboard Sections

### Collateral Pool
Full bond inventory with live pricing (OIS curve), haircuts per ICMA/ECB framework, HQLA tier, ECB eligibility, modified duration.

### Haircut Matrix
Colour-coded haircut grid by asset class × rating × maturity bucket. Implements the ICMA GMRA / ECB collateral framework logic.

### Repo Book
All repo positions with:
- **Initial Margin (IM)** — SIMM-inspired: `notional × vol × √(MPoR/252) × z-score`
- **Variation Margin (VM)** — `collateral value after haircut − repo notional`
- Threshold, MTA (Minimum Transfer Amount), and rounding applied per CSA/GMRA terms

### Margin Calls
Real-time status per counterparty: OK / MONITOR (>70% of threshold) / CALL triggered. Call amount computed after threshold + MTA + rounding.

### Stress Scenarios
Parallel rate shift (−200bp to +200bp) applied to all collateral bonds:
- Per-repo impact on market value and collateral value
- New margin calls triggered by the scenario
- Sensitivity curve: number of calls and CV change vs. rate shift



## Regulatory References
- ICMA Global Master Repo Agreement (GMRA)
- ECB Collateral Framework (Guideline ECB/2014/60)
- BCBS/IOSCO Margin Requirements for Non-Centrally Cleared Derivatives
- ISDA SIMM — Standard Initial Margin Model
