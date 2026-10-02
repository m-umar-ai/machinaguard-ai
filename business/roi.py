"""ROI + pricing model. EVERY default below is an ASSUMPTION to be replaced with a pilot customer's real figures."""
from __future__ import annotations

DEFAULTS = {"machines": 20, "failures_per_machine_year": 0.5, "unplanned_downtime_hours": 16.0, "planned_downtime_hours": 2.5,
            "cost_per_downtime_hour_usd": 800.0, "detection_rate": 0.8, "avoidable_fraction": 0.7,
            "price_per_machine_month_usd": 40.0, "setup_fee_usd": 1500.0, "fx_pkr_per_usd": 280.0}
TIERS = {"Starter (1-10 machines)": 55.0, "Plant (11-50 machines)": 40.0, "Enterprise (50+ machines)": 28.0}


def roi(**kw) -> dict:
    a = {**DEFAULTS, **kw}
    failures = a["machines"] * a["failures_per_machine_year"]
    avoided = failures * a["detection_rate"] * a["avoidable_fraction"]
    hours_saved = avoided * max(a["unplanned_downtime_hours"] - a["planned_downtime_hours"], 0.0)
    gross = hours_saved * a["cost_per_downtime_hour_usd"]
    subscription = a["machines"] * a["price_per_machine_month_usd"] * 12
    year1_cost = subscription + a["setup_fee_usd"]
    net = gross - year1_cost
    monthly_net = (gross - subscription) / 12
    payback = a["setup_fee_usd"] / monthly_net if monthly_net > 0 else None
    per_unit_gain = (a["cost_per_downtime_hour_usd"] * max(a["unplanned_downtime_hours"] - a["planned_downtime_hours"], 0.0)
                     * a["failures_per_machine_year"] * a["avoidable_fraction"])
    be_detect = (subscription / a["machines"]) / per_unit_gain if per_unit_gain > 0 else None
    fx = a["fx_pkr_per_usd"]
    return {"inputs": a, "failures_per_year": round(failures, 1), "failures_avoided_per_year": round(avoided, 2), "downtime_hours_saved": round(hours_saved, 1),
            "gross_savings_usd": round(gross), "subscription_usd": round(subscription), "year1_net_usd": round(net),
            "roi_pct": round(100 * net / year1_cost, 1) if year1_cost else None, "payback_months": round(payback, 1) if payback else None,
            "break_even_detection_rate": round(be_detect, 2) if be_detect else None,
            "gross_savings_pkr": round(gross * fx), "year1_net_pkr": round(net * fx)}


def sensitivity(base: dict | None = None, rates=(0.5, 0.65, 0.8, 0.9), costs=(300, 600, 800, 1500)) -> list[dict]:
    base = base or {}
    return [{"detection_rate": r, **{f"${c}/h": roi(**{**base, "detection_rate": r, "cost_per_downtime_hour_usd": c})["year1_net_usd"] for c in costs}} for r in rates]
