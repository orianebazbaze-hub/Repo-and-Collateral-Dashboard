"""
Collateral Management Dashboard — Flask Backend
================================================
Corporate Treasury | Repo & Collateral Management

Covers:
  - Collateral pool with haircuts by asset class / rating / maturity
  - Repo book (bilateral + triparty)
  - Initial Margin (IM) and Variation Margin (VM) computation
  - Margin call trigger logic (threshold, MTA, rounding)
  - Stress scenarios on bond prices → margin impact
  - Eligible collateral substitution

Run
---
    pip install flask flask-cors numpy scipy pandas
    python app.py  →  http://localhost:5001
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import numpy as np
from scipy.interpolate import CubicSpline
import math

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Market data — EUR OIS curve (approximate April 2026 levels)
# ---------------------------------------------------------------------------
TENORS = np.array([0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30])
RATES  = np.array([0.0350, 0.0340, 0.0320, 0.0290, 0.0275, 0.0260,
                   0.0252, 0.0248, 0.0245, 0.0242, 0.0238])
_curve = CubicSpline(TENORS, RATES, bc_type="natural")

def discount(t):
    t = np.asarray(t, dtype=float)
    return np.exp(-_curve(t) * t)

def bond_price(coupon, maturity, freq=2):
    dt = 1 / freq
    times = np.arange(dt, maturity + dt/2, dt)
    flows = np.full(len(times), 100 * coupon / freq)
    flows[-1] += 100
    return float(np.sum(flows * discount(times)))

def bond_price_stressed(coupon, maturity, shift_bp, freq=2):
    dt = 1 / freq
    times = np.arange(dt, maturity + dt/2, dt)
    flows = np.full(len(times), 100 * coupon / freq)
    flows[-1] += 100
    stressed_rates = _curve(times) + shift_bp * 1e-4
    dfs = np.exp(-stressed_rates * times)
    return float(np.sum(flows * dfs))

def mod_duration(coupon, maturity, freq=2):
    dt = 1 / freq
    times = np.arange(dt, maturity + dt/2, dt)
    flows = np.full(len(times), 100 * coupon / freq)
    flows[-1] += 100
    dfs = discount(times)
    px = float(np.sum(flows * dfs))
    mac = float(np.sum(times * flows * dfs)) / px
    y = _curve(maturity)
    return mac / (1 + y / freq)

# ---------------------------------------------------------------------------
# Haircut matrix
# ICMA / ECB eligibility framework
# Haircut = f(asset_class, rating, maturity_bucket)
# ---------------------------------------------------------------------------
HAIRCUT_MATRIX = {
    # (asset_class, rating_bucket, maturity_bucket) → haircut %
    ("govt",   "AAA-AA", "0-1Y"):   0.5,
    ("govt",   "AAA-AA", "1-3Y"):   1.0,
    ("govt",   "AAA-AA", "3-5Y"):   1.5,
    ("govt",   "AAA-AA", "5-7Y"):   2.0,
    ("govt",   "AAA-AA", "7-10Y"):  2.5,
    ("govt",   "AAA-AA", "10Y+"):   3.5,
    ("govt",   "A",      "0-1Y"):   1.0,
    ("govt",   "A",      "1-3Y"):   1.5,
    ("govt",   "A",      "3-5Y"):   2.5,
    ("govt",   "A",      "5-7Y"):   3.0,
    ("govt",   "A",      "7-10Y"):  3.5,
    ("govt",   "A",      "10Y+"):   4.5,
    ("agency", "AAA-AA", "0-1Y"):   1.0,
    ("agency", "AAA-AA", "1-3Y"):   2.0,
    ("agency", "AAA-AA", "3-5Y"):   2.5,
    ("agency", "AAA-AA", "5-7Y"):   3.0,
    ("agency", "AAA-AA", "7-10Y"):  3.5,
    ("agency", "AAA-AA", "10Y+"):   4.5,
    ("covered","AAA-AA", "0-1Y"):   1.0,
    ("covered","AAA-AA", "1-3Y"):   2.0,
    ("covered","AAA-AA", "3-5Y"):   3.0,
    ("covered","AAA-AA", "5-7Y"):   3.5,
    ("covered","AAA-AA", "7-10Y"):  4.0,
    ("covered","AAA-AA", "10Y+"):   5.0,
    ("corp",   "AAA-AA", "0-1Y"):   1.5,
    ("corp",   "AAA-AA", "1-3Y"):   3.0,
    ("corp",   "AAA-AA", "3-5Y"):   5.0,
    ("corp",   "AAA-AA", "5-7Y"):   6.0,
    ("corp",   "AAA-AA", "7-10Y"):  7.0,
    ("corp",   "AAA-AA", "10Y+"):   8.5,
    ("corp",   "A",      "0-1Y"):   2.0,
    ("corp",   "A",      "1-3Y"):   4.0,
    ("corp",   "A",      "3-5Y"):   6.0,
    ("corp",   "A",      "5-7Y"):   7.5,
    ("corp",   "A",      "7-10Y"):  9.0,
    ("corp",   "A",      "10Y+"):   11.0,
}

def get_haircut(asset_class, rating, maturity):
    if maturity <= 1:   bucket = "0-1Y"
    elif maturity <= 3: bucket = "1-3Y"
    elif maturity <= 5: bucket = "3-5Y"
    elif maturity <= 7: bucket = "5-7Y"
    elif maturity <= 10:bucket = "7-10Y"
    else:               bucket = "10Y+"
    key = (asset_class, rating, bucket)
    return HAIRCUT_MATRIX.get(key, 5.0)

# ---------------------------------------------------------------------------
# Collateral pool
# ---------------------------------------------------------------------------
COLLATERAL_POOL = [
    {"id": "C01", "label": "OAT 3% 2034",      "asset_class": "govt",    "rating": "AA",    "rating_bucket": "AAA-AA", "coupon": 0.030, "maturity": 8.5,  "face": 50_000_000,  "hqla": "L1",   "ecb_eligible": True},
    {"id": "C02", "label": "Bund 2.5% 2029",    "asset_class": "govt",    "rating": "AAA",   "rating_bucket": "AAA-AA", "coupon": 0.025, "maturity": 3.5,  "face": 40_000_000,  "hqla": "L1",   "ecb_eligible": True},
    {"id": "C03", "label": "BTP 4% 2031",        "asset_class": "govt",    "rating": "A",     "rating_bucket": "A",      "coupon": 0.040, "maturity": 5.5,  "face": 30_000_000,  "hqla": "L1",   "ecb_eligible": True},
    {"id": "C04", "label": "KfW 2.75% 2030",     "asset_class": "agency",  "rating": "AAA",   "rating_bucket": "AAA-AA", "coupon": 0.0275,"maturity": 4.5,  "face": 25_000_000,  "hqla": "L2A",  "ecb_eligible": True},
    {"id": "C05", "label": "CADES 3% 2033",      "asset_class": "agency",  "rating": "AA",    "rating_bucket": "AAA-AA", "coupon": 0.030, "maturity": 7.2,  "face": 20_000_000,  "hqla": "L2A",  "ecb_eligible": True},
    {"id": "C06", "label": "CRH Cover 3.5% 2028","asset_class": "covered", "rating": "AAA",   "rating_bucket": "AAA-AA", "coupon": 0.035, "maturity": 2.8,  "face": 15_000_000,  "hqla": "L2A",  "ecb_eligible": True},
    {"id": "C07", "label": "LVMH 2% 2027",       "asset_class": "corp",    "rating": "A+",    "rating_bucket": "AAA-AA", "coupon": 0.020, "maturity": 1.5,  "face": 10_000_000,  "hqla": "L2B",  "ecb_eligible": False},
    {"id": "C08", "label": "Total 3.125% 2032",  "asset_class": "corp",    "rating": "A",     "rating_bucket": "A",      "coupon": 0.03125,"maturity": 6.5, "face": 12_000_000,  "hqla": "L2B",  "ecb_eligible": False},
]

# ---------------------------------------------------------------------------
# Repo book
# ---------------------------------------------------------------------------
REPO_BOOK = [
    {"id": "R01", "counterparty": "BNP Paribas",      "collateral_id": "C01", "notional": 45_000_000, "repo_rate": 0.0355, "maturity_days": 7,   "type": "bilateral", "threshold": 500_000,  "mta": 100_000, "rounding": 50_000},
    {"id": "R02", "counterparty": "Société Générale",  "collateral_id": "C02", "notional": 35_000_000, "repo_rate": 0.0348, "maturity_days": 14,  "type": "bilateral", "threshold": 300_000,  "mta": 75_000,  "rounding": 25_000},
    {"id": "R03", "counterparty": "Deutsche Bank",     "collateral_id": "C03", "notional": 25_000_000, "repo_rate": 0.0360, "maturity_days": 30,  "type": "bilateral", "threshold": 400_000,  "mta": 100_000, "rounding": 50_000},
    {"id": "R04", "counterparty": "HSBC",           "agent": "Euroclear",   "collateral_id": "C04", "notional": 20_000_000, "repo_rate": 0.0352, "maturity_days": 7,  "type": "triparty",  "threshold": 250_000, "mta": 50_000,  "rounding": 10_000},
    {"id": "R05", "counterparty": "JP Morgan",         "collateral_id": "C05", "notional": 15_000_000, "repo_rate": 0.0358, "maturity_days": 1,   "type": "bilateral", "threshold": 200_000,  "mta": 50_000,  "rounding": 25_000},
    {"id": "R06", "counterparty": "Natixis",        "agent": "Clearstream", "collateral_id": "C06", "notional": 12_000_000, "repo_rate": 0.0345, "maturity_days": 1,  "type": "triparty",  "threshold": 150_000, "mta": 25_000,  "rounding": 10_000},
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def maturity_bucket(m):
    if m <= 1:    return "0-1Y"
    elif m <= 3:  return "1-3Y"
    elif m <= 5:  return "3-5Y"
    elif m <= 7:  return "5-7Y"
    elif m <= 10: return "7-10Y"
    else:         return "10Y+"

def round_to(value, multiple):
    if multiple <= 0: return value
    return round(round(value / multiple) * multiple, 2)

def compute_vm(market_value, haircut_pct, notional, threshold, mta, rounding):
    """
    Variation Margin = collateral value after haircut - repo notional.
    Positive VM = bank has excess collateral (over-collateralised).
    Negative VM = bank needs to post additional collateral (margin call).
    """
    collateral_value = market_value * (1 - haircut_pct / 100)
    exposure = collateral_value - notional
    # Margin call triggered if |exposure| > threshold + MTA
    call_amount_raw = exposure - threshold if exposure < 0 else 0
    if abs(call_amount_raw) > mta:
        call_amount = round_to(call_amount_raw, rounding)
    else:
        call_amount = 0
    return {
        "market_value": round(market_value, 2),
        "collateral_value": round(collateral_value, 2),
        "exposure": round(exposure, 2),
        "vm": round(exposure, 2),
        "call_triggered": call_amount != 0,
        "call_amount": round(call_amount, 2),
    }

def compute_im(notional, maturity_days, vol_bp=80, confidence=0.99):
    """
    Simplified IM using a SIMM-inspired approach:
    IM ≈ notional × vol × sqrt(MPoR/252) × z-score
    MPoR = Margin Period of Risk (typically 5 days for bilateral, 2 for triparty)
    """
    mpor = 5 if maturity_days > 1 else 2
    z = 2.326 if confidence == 0.99 else 1.645
    vol_decimal = vol_bp * 1e-4
    im = notional * vol_decimal * math.sqrt(mpor / 252) * z
    return round(im, 2)

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/pool")
def api_pool():
    rows = []
    total_mv = 0
    total_cv = 0
    for c in COLLATERAL_POOL:
        px = bond_price(c["coupon"], c["maturity"])
        mv = px / 100 * c["face"]
        hc = get_haircut(c["asset_class"], c["rating_bucket"], c["maturity"])
        cv = mv * (1 - hc / 100)
        dur = mod_duration(c["coupon"], c["maturity"])
        total_mv += mv
        total_cv += cv
        rows.append({
            "id": c["id"],
            "label": c["label"],
            "asset_class": c["asset_class"],
            "rating": c["rating"],
            "maturity": round(c["maturity"], 1),
            "maturity_bucket": maturity_bucket(c["maturity"]),
            "face": c["face"],
            "price": round(px, 4),
            "market_value": round(mv, 2),
            "haircut": round(hc, 2),
            "collateral_value": round(cv, 2),
            "duration": round(dur, 3),
            "hqla": c["hqla"],
            "ecb_eligible": c["ecb_eligible"],
        })
    return jsonify({
        "pool": rows,
        "total_market_value": round(total_mv, 2),
        "total_collateral_value": round(total_cv, 2),
        "utilisation_pct": round(total_cv / total_mv * 100, 2) if total_mv else 0,
    })


@app.route("/api/repo")
def api_repo():
    pool_map = {c["id"]: c for c in COLLATERAL_POOL}
    rows = []
    total_notional = 0
    total_im = 0
    margin_calls = 0

    for r in REPO_BOOK:
        c = pool_map[r["collateral_id"]]
        px = bond_price(c["coupon"], c["maturity"])
        mv = px / 100 * c["face"]
        hc = get_haircut(c["asset_class"], c["rating_bucket"], c["maturity"])
        vm_data = compute_vm(mv, hc, r["notional"], r["threshold"], r["mta"], r["rounding"])
        im = compute_im(r["notional"], r["maturity_days"])
        accrued = r["notional"] * r["repo_rate"] * r["maturity_days"] / 360
        total_notional += r["notional"]
        total_im += im
        if vm_data["call_triggered"]:
            margin_calls += 1
        rows.append({
            "id": r["id"],
            "counterparty": r["counterparty"],
            "agent": r.get("agent"),
            "collateral": c["label"],
            "collateral_id": c["id"],
            "notional": r["notional"],
            "repo_rate": round(r["repo_rate"] * 100, 4),
            "maturity_days": r["maturity_days"],
            "type": r["type"],
            "haircut": round(hc, 2),
            "threshold": r["threshold"],
            "mta": r["mta"],
            "accrued_interest": round(accrued, 2),
            "initial_margin": im,
            **vm_data,
        })

    return jsonify({
        "repos": rows,
        "total_notional": round(total_notional, 2),
        "total_im": round(total_im, 2),
        "margin_calls": margin_calls,
        "summary": {
            "bilateral": sum(1 for r in REPO_BOOK if r["type"] == "bilateral"),
            "triparty":  sum(1 for r in REPO_BOOK if r["type"] == "triparty"),
        }
    })


@app.route("/api/haircuts")
def api_haircuts():
    buckets = ["0-1Y", "1-3Y", "3-5Y", "5-7Y", "7-10Y", "10Y+"]
    classes = [
        ("govt",    "AAA-AA", "Sovereign AAA-AA"),
        ("govt",    "A",      "Sovereign A"),
        ("agency",  "AAA-AA", "Agency AAA-AA"),
        ("covered", "AAA-AA", "Covered Bond AAA-AA"),
        ("corp",    "AAA-AA", "Corp IG AAA-AA"),
        ("corp",    "A",      "Corp IG A"),
    ]
    matrix = []
    for (ac, rb, label) in classes:
        row = {"label": label, "buckets": {}}
        for b in buckets:
            row["buckets"][b] = HAIRCUT_MATRIX.get((ac, rb, b), None)
        matrix.append(row)
    return jsonify({"matrix": matrix, "buckets": buckets})


@app.route("/api/stress")
def api_stress():
    shift_bp = float(request.args.get("shift", 100))
    pool_map = {c["id"]: c for c in COLLATERAL_POOL}

    results = []
    total_mv_base = 0
    total_mv_stress = 0
    total_cv_base = 0
    total_cv_stress = 0
    calls_triggered = 0

    for r in REPO_BOOK:
        c = pool_map[r["collateral_id"]]
        px_base   = bond_price(c["coupon"], c["maturity"])
        px_stress = bond_price_stressed(c["coupon"], c["maturity"], shift_bp)
        mv_base   = px_base   / 100 * c["face"]
        mv_stress = px_stress / 100 * c["face"]
        hc = get_haircut(c["asset_class"], c["rating_bucket"], c["maturity"])
        cv_base   = mv_base   * (1 - hc / 100)
        cv_stress = mv_stress * (1 - hc / 100)

        vm_base   = compute_vm(mv_base,   hc, r["notional"], r["threshold"], r["mta"], r["rounding"])
        vm_stress = compute_vm(mv_stress, hc, r["notional"], r["threshold"], r["mta"], r["rounding"])

        total_mv_base   += mv_base
        total_mv_stress += mv_stress
        total_cv_base   += cv_base
        total_cv_stress += cv_stress
        if vm_stress["call_triggered"]:
            calls_triggered += 1

        results.append({
            "repo_id": r["id"],
            "counterparty": r["counterparty"],
            "collateral": c["label"],
            "notional": r["notional"],
            "px_base": round(px_base, 4),
            "px_stress": round(px_stress, 4),
            "px_change": round(px_stress - px_base, 4),
            "mv_base": round(mv_base, 2),
            "mv_stress": round(mv_stress, 2),
            "mv_change": round(mv_stress - mv_base, 2),
            "cv_base": round(cv_base, 2),
            "cv_stress": round(cv_stress, 2),
            "vm_base": vm_base["vm"],
            "vm_stress": vm_stress["vm"],
            "call_base": vm_base["call_triggered"],
            "call_stress": vm_stress["call_triggered"],
            "call_amount_stress": vm_stress["call_amount"],
            "new_call": vm_stress["call_triggered"] and not vm_base["call_triggered"],
        })

    scenarios = []
    for shift in [-200, -150, -100, -50, 0, 50, 100, 150, 200]:
        agg_mv = 0
        agg_cv = 0
        agg_calls = 0
        agg_call_amount = 0
        for r in REPO_BOOK:
            c = pool_map[r["collateral_id"]]
            px_s = bond_price_stressed(c["coupon"], c["maturity"], shift)
            mv_s = px_s / 100 * c["face"]
            hc   = get_haircut(c["asset_class"], c["rating_bucket"], c["maturity"])
            cv_s = mv_s * (1 - hc / 100)
            vm_s = compute_vm(mv_s, hc, r["notional"], r["threshold"], r["mta"], r["rounding"])
            agg_mv += mv_s
            agg_cv += cv_s
            if vm_s["call_triggered"]:
                agg_calls += 1
                agg_call_amount += abs(vm_s["call_amount"])
        scenarios.append({
            "shift": shift,
            "total_mv": round(agg_mv, 2),
            "total_cv": round(agg_cv, 2),
            "margin_calls": agg_calls,
            "total_call_amount": round(agg_call_amount, 2),
        })

    return jsonify({
        "shift_bp": shift_bp,
        "repos": results,
        "total_mv_base": round(total_mv_base, 2),
        "total_mv_stress": round(total_mv_stress, 2),
        "total_mv_change": round(total_mv_stress - total_mv_base, 2),
        "total_cv_base": round(total_cv_base, 2),
        "total_cv_stress": round(total_cv_stress, 2),
        "calls_triggered": calls_triggered,
        "scenarios": scenarios,
    })


@app.route("/api/margin_calls")
def api_margin_calls():
    pool_map = {c["id"]: c for c in COLLATERAL_POOL}
    calls = []
    for r in REPO_BOOK:
        c = pool_map[r["collateral_id"]]
        px = bond_price(c["coupon"], c["maturity"])
        mv = px / 100 * c["face"]
        hc = get_haircut(c["asset_class"], c["rating_bucket"], c["maturity"])
        vm_data = compute_vm(mv, hc, r["notional"], r["threshold"], r["mta"], r["rounding"])
        im = compute_im(r["notional"], r["maturity_days"])
        calls.append({
            "repo_id": r["id"],
            "counterparty": r["counterparty"],
            "collateral": c["label"],
            "notional": r["notional"],
            "threshold": r["threshold"],
            "mta": r["mta"],
            "rounding": r["rounding"],
            "im": im,
            "vm": vm_data["vm"],
            "exposure": vm_data["exposure"],
            "call_triggered": vm_data["call_triggered"],
            "call_amount": vm_data["call_amount"],
            "status": "CALL" if vm_data["call_triggered"] else (
                "MONITOR" if abs(vm_data["vm"]) > r["threshold"] * 0.7 else "OK"
            ),
        })
    return jsonify({"calls": calls})


if __name__ == "__main__":
    print("Collateral Dashboard running at http://localhost:5001")
    app.run(debug=True, port=5001)
