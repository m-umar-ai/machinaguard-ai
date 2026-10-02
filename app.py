"""MachinaGuard AI - AI operations control center (Streamlit)."""
import html as _html, json, time
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from core import MachineSession
from utils.config import UNITS, llm_name
from business.roi import roi, sensitivity, TIERS, DEFAULTS
from genai.assistant import ask as ask_machine
from genai.reports import shift_report, whatsapp_alert
from rag.evaluate import evaluate as rag_eval

st.set_page_config(page_title="MachinaGuard AI", page_icon="🛡️", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.2rem}
.card{background:#111827;border:1px solid #243049;border-radius:12px;padding:12px 16px;color:#e5e7eb}
.card h4{margin:0;font-size:.8rem;color:#94a3b8;font-weight:500}.card .v{font-size:1.7rem;font-weight:700}
.NORMAL{color:#22c55e}.WARNING{color:#f59e0b}.CRITICAL{color:#ef4444}.UNKNOWN{color:#94a3b8}
.stage{display:inline-block;padding:6px 12px;border-radius:8px;margin:2px;font-size:.85rem;border:1px solid #243049}
.done{background:#052e1b;color:#86efac}.active{background:#3b2a05;color:#fcd34d;border-color:#f59e0b}.pending{background:#111827;color:#64748b}
.sim{background:#3b2a05;color:#fcd34d;padding:2px 8px;border-radius:6px;font-weight:700;font-size:.8rem}
</style>""", unsafe_allow_html=True)

if "S" not in st.session_state:
    st.session_state.S = MachineSession()
S: MachineSession = st.session_state.S

# ---------------- sidebar controls ----------------
with st.sidebar:
    st.title("🛡️ MachinaGuard AI")
    st.caption("Detect the failure before the machine does.")
    c1, c2 = st.columns(2)
    if c1.button("▶ START", width="stretch"): S.running = True
    if c2.button("⏸ STOP", width="stretch"): S.running = False
    if st.button("🔄 RESET MACHINE", width="stretch"): S.reset(); st.rerun()
    st.divider()
    if st.button("🎬 DEMO MODE", type="primary", width="stretch"): S.start_demo(); st.rerun()
    if st.button("🚨 SIMULATE DEVELOPING FAILURE", width="stretch"): S.simulate_failure(); S.running = True
    if st.button("⚠️ INJECT SENSOR FAULT", width="stretch"): S.inject_fault(); S.running = True
    if st.button("🔧 Complete maintenance (sim)", width="stretch"): S.complete_maintenance()
    if st.button("🎯 Calibrate to this machine", width="stretch", help="Learn this machine's healthy baseline (run 200+ healthy ticks first)"):
        st.toast("Calibrated on this machine's healthy data" if S.calibrate() else "Need 200+ healthy ticks and no open incident", icon="🎯")
    speed = st.slider("Seconds per tick", 0.3, 3.0, 1.5, 0.1)
    st.divider()
    st.markdown("**Mode:** " + ("🟠 OFFLINE MODE - rule-based planner, templates (no LLM key)" if S.offline else f"🟢 LLM agents · {llm_name()}"))
    st.caption("Machine M-04 · all maintenance actions are SIMULATED")

ml = S.ml
status = ml.get("status", "UNKNOWN")
df = S.engine.frame(120)
inc = S.incident
res = inc["result"] if inc else None

# ---------------- header cards ----------------
icon = {"NORMAL": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}.get(status, "⚪")
risk_txt = f'{res["risk"]["level"]} ({res["risk"]["failure_risk"]:.0%})' if res else "LOW"
cols = st.columns(5)
for col, (t, v, cls) in zip(cols, [
    ("MACHINE M-04", f"{icon} {status}", status), ("ANOMALY SCORE", f'{ml.get("anomaly_score", 0):.2f}', status),
    ("RISK LEVEL", risk_txt, status), ("AGENT CONFIDENCE", f'{res["decision"]["confidence"]:.0%}' if res else "—", "UNKNOWN"),
    ("TICK", f"{S.tick_n}" + (" · DEMO" if S.demo else ""), "UNKNOWN")]):
    col.markdown(f'<div class="card"><h4>{t}</h4><div class="v {cls}">{v}</div></div>', unsafe_allow_html=True)

# ---------------- live charts ----------------
st.write("")
fig = make_subplots(rows=2, cols=3, subplot_titles=["Temperature °C", "Vibration mm/s (A vs B)", "Pressure bar", "Energy kW", "Production units/h", "Anomaly score"], vertical_spacing=0.18)
x = df["timestamp"]
pos = {"temperature": (1, 1), "pressure": (1, 3), "energy": (2, 1), "production_rate": (2, 2)}
for k, (r, c) in pos.items():
    fig.add_trace(go.Scatter(x=x, y=df[k], mode="lines", name=k, line=dict(width=2)), row=r, col=c)
fig.add_trace(go.Scatter(x=x, y=df["vibration"], name="vibration A", line=dict(width=2)), row=1, col=2)
fig.add_trace(go.Scatter(x=x, y=df["vibration_b"], name="vibration B", line=dict(width=2, dash="dot")), row=1, col=2)
sc = S.scores[-120:]
fig.add_trace(go.Scatter(y=sc, mode="lines", name="anomaly", fill="tozeroy", line=dict(color="#ef4444")), row=2, col=3)
fig.update_layout(height=430, template="plotly_dark", showlegend=False, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, width="stretch")

# ---------------- agent strip ----------------
st.markdown("**AI AGENTS**  " + "  ·  ".join(f"{s} {n}" for n, s in S.agent_states()))

tab1, tab2, tabA, tab3, tab4, tabQ, tabR, tabB, tabV = st.tabs(["🧭 Command Center", "📚 Evidence (RAG)", "🤖 Agent Trace", "🧠 Decision & Critic", "✅ Approval & Process",
                                                              "💬 Ask the Machine", "📝 Reports EN/اردو", "💼 Business & ROI", "📊 Validation"])

with tab1:
    a, b = st.columns([1, 1])
    with a:
        st.subheader("Event timeline")
        for e in reversed(S.timeline[-14:]):
            st.markdown(f"`{e['time']}` **{e['agent']}** — {e['text']}")
        if not S.timeline: st.caption("Waiting for events. Press START, DEMO MODE or SIMULATE DEVELOPING FAILURE.")
    with b:
        st.subheader("Decision trace")
        html = "".join(f'<div class="stage {s}">{"✔" if s=="done" else "●" if s=="active" else "○"} {n}</div><div style="text-align:center;color:#475569">↓</div>' for n, s in S.stage_states())
        st.markdown(html.rsplit('<div style="text-align:center', 1)[0], unsafe_allow_html=True)

with tab2:
    if res and inc["reveal"] >= 4 and res["rag"]["results"]:
        st.caption(f'Query: {res["rag"]["query"]}  ·  hybrid BM25 + TF-IDF(FAISS) + LSA over {len(S.kb.chunks)} sections / {len({c["file"] for c in S.kb.chunks})} documents · evidence-gated (abstains when nothing relevant)')
        for r in res["rag"]["results"]:
            with st.expander(f'[{r["cid"]}] {r["document"]} — {r["section"]}  (relevance {r["relevance"]})', expanded=True):
                st.write(r["text"])
    else:
        st.info("No retrieval yet - triggered when an anomaly is investigated.")

with tabA:
    inv = res["investigation"] if res else None
    if inv and inc["reveal"] >= 5 and inv.get("final"):
        st.markdown(f'#### 🤖 Investigator Agent — mode: `{inv["mode"]}`')
        st.caption("Tool-using agent: it chooses tools, reads their results, then ranks hypotheses. It can only recommend - it cannot act.")
        for t in inv["trace"]:
            with st.expander(f'Step {t["step"]} · **{t["tool"]}** {json.dumps(t["args"]) if t["args"] else ""}'):
                st.caption("Thought: " + (t["thought"] or "-"))
                st.json(t["observation"])
        f = inv["final"]
        st.markdown("**Ranked hypotheses**")
        st.dataframe(pd.DataFrame([{"cause": h["cause"], "likelihood": h["likelihood"], "evidence": "; ".join(h["evidence"])} for h in f["hypotheses"]]), hide_index=True, width="stretch")
        st.markdown("**Recommended checks:** " + "; ".join(f["recommended_checks"]))
        st.markdown("**Citations (verified against retrieved passages):** " + (", ".join(f["citations"]) or "none"))
        st.info(f["summary"])
    else:
        st.info("Appears when an anomaly is investigated: you will see every tool call the agent makes.")

with tab3:
    if res and inc["reveal"] >= 7:
        d, cr, dg = res["decision"], res["critic"], res["diagnosis"]
        l, r = st.columns(2)
        with l:
            st.markdown("#### 🔎 Observed data")
            for o in d["observed_data"]: st.markdown(f"- {o}")
            st.markdown("#### 🧠 AI interpretation")
            st.write(dg["summary"])
            st.progress(float(dg["confidence"]), text=f'Diagnosis confidence {dg["confidence"]:.0%} (not a confirmed fact)')
            if dg["alternatives"]:
                st.caption("Alternatives: " + ", ".join(f'{a["cause"]} ({a["weight"]:.0%})' for a in dg["alternatives"]))
        with r:
            st.markdown(f"#### 🛑 Critic Agent — {cr['verdict']}")
            for it in cr["items"]:
                if it.get("source"): st.caption("🧪 " + it["source"])
                st.markdown(f"**Evidence:** {it['evidence']}  \n**Finding:** {it['finding']}  \n**Concern:** {it['concern']}  \n**Recommendation:** {it['recommendation']}")
                st.divider()
        if inc["reveal"] >= 8:
            st.markdown("#### ⚖️ Decision (Recommendation)")
            st.success(f'**{d["problem"]}** → {d["recommended_action"]}')
            st.write(d["reason"]); st.caption(d["executive_summary"])
            rk = res["risk"]
            st.markdown(f'**Risk:** {rk["summary"]}  \n<span class="sim">SIMULATED</span> {rk["assumptions_note"]}', unsafe_allow_html=True)
            if d["missing_information"]: st.markdown("**Missing information:** " + "; ".join(d["missing_information"]))
            st.metric("Final confidence (after critic)", f'{d["confidence"]:.0%}')
    else:
        st.info("The agents will populate this once an anomaly is detected.")

with tab4:
    if res and inc["reveal"] >= 9 and res["decision"]["requires_approval"]:
        gate = inc["gate"]
        st.markdown(f'### Human approval: **{gate.state}**')
        st.write(f'Proposed: {res["decision"]["recommended_action"]}')
        if gate.state == "PENDING":
            c1, c2 = st.columns(2)
            if c1.button("✅ APPROVE ACTION", type="primary", width="stretch"): S.approve(); st.rerun()
            if c2.button("🛑 REJECT / REQUEST REVIEW", width="stretch"): S.reject(); st.rerun()
        wf = inc["workflow"]
        st.caption(wf["summary"])
        if wf["ticket"]:
            t = wf["ticket"]
            st.markdown(f'<span class="sim">SIMULATED WORKFLOW</span> **{t["ticket_id"]}**', unsafe_allow_html=True)
            ("telegram")
        
            st.json({k: v for k, v in t.items() if k not in ("technician_checklist", "escalation_message", "label", "process")})
            pr = t.get("process")
            if pr:
                st.markdown(f'#### ⚙️ Business-process automation — **{pr["state"]}**')
                c1, c2, c3 = st.columns(3)
                c1.metric("Technician", pr["technician"] or "none"); c2.metric("SLA (hours)", pr["sla_hours"]); c3.metric("Scheduled start", pr["scheduled_start"].replace("T", " "))
                st.dataframe(pd.DataFrame(pr["parts"]), hide_index=True, width="stretch")
                if pr["purchase_request"]: st.warning(f'{pr["purchase_request"]["status"]}: ' + ", ".join(pr["purchase_request"]["items"]))
                st.markdown("**Audit log**")
                st.dataframe(pd.DataFrame(pr["audit_log"]), hide_index=True, width="stretch")
                for n in pr["notifications"]:
                    st.markdown(f'**Draft notification ({n["lang"].upper()})** · {n["method"]}')
                    st.markdown(f'<div dir="{"rtl" if n["lang"] == "ur" else "ltr"}" style="background:#111827;padding:10px;border-radius:8px">{_html.escape(n["text"]).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
            st.markdown("**Technician checklist**")
            for i, c in enumerate(t["technician_checklist"], 1): st.checkbox(c, key=f"chk{i}{t['ticket_id']}")
            st.text_area("Escalation message (simulated)", t["escalation_message"], height=110)
    else:
        st.info("No approval pending. The system never acts on its own.")

with tabQ:
    st.caption("Ask in plain English. With an LLM key this is a tool-using agent; offline it uses an intent router + grounded RAG (abstains when the manuals don't cover it).")
    with st.form("askform", clear_on_submit=False):
        q = st.text_input("Question", placeholder="e.g. Can I trust the vibration sensor?  /  How do I lock out a machine?  /  What is the risk?")
        go = st.form_submit_button("Ask")
    if go and q:
        S.running = False  # pause the live loop so the answer stays on screen
        st.session_state["ask"] = ask_machine(q, S.engine.frame(120), S.detector, S.kb, S._trend())
    a = st.session_state.get("ask")
    if a:
        st.success(a["answer"]); st.caption(f'Method: {a["method"]}')
        if a.get("llm_error"): st.warning(f'LLM call failed, used offline fallback. Reason: {a["llm_error"]}')
        for c in a["citations"]: st.markdown(f'📎 **[{c["cid"]}]** {c["document"]} — {c["section"]}')
        if a["trace"]:
            with st.expander("Tool trace"): st.json([{k: t[k] for k in ("tool", "args", "observation")} for t in a["trace"]])
    st.caption("Tip: press STOP before asking; START resumes monitoring.")

with tabR:
    st.caption("GenAI communication layer. English + Urdu. LLM polishes if configured; otherwise labelled bilingual templates.")
    if st.button("Generate shift report + alerts"):
        S.running = False
        d = res["decision"] if res else None
        st.session_state["rep"] = {"sr_en": shift_report(S.timeline, inc, ml, "en"), "sr_ur": shift_report(S.timeline, inc, ml, "ur"),
                                   "wa_en": whatsapp_alert(d, res["risk"], "en") if d else None, "wa_ur": whatsapp_alert(d, res["risk"], "ur") if d else None}
    rep = st.session_state.get("rep")
    if rep:
        for key, title in (("sr_en", "Shift report (EN)"), ("sr_ur", "شفٹ رپورٹ (اردو)"), ("wa_en", "WhatsApp alert (EN)"), ("wa_ur", "واٹس ایپ الرٹ (اردو)")):
            r = rep.get(key)
            if r:
                st.markdown(f"**{title}** · _{r['method']}_")
                st.markdown(f'<div dir="{"rtl" if r["lang"] == "ur" else "ltr"}" style="background:#111827;padding:12px;border-radius:8px;font-size:1.05rem">{_html.escape(r["text"]).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

with tabB:
    st.caption("Every number below is an ASSUMPTION - replace with the pilot customer's real figures. Nothing here is a market claim.")
    cur = st.radio("Currency", ["USD", "PKR"], horizontal=True)
    c1, c2, c3 = st.columns(3)
    machines = c1.number_input("Machines monitored", 1, 2000, DEFAULTS["machines"])
    fails = c1.number_input("Failures / machine / year", 0.0, 5.0, DEFAULTS["failures_per_machine_year"], 0.1)
    cost_h = c2.number_input("Cost per downtime hour (USD)", 50.0, 20000.0, DEFAULTS["cost_per_downtime_hour_usd"], 50.0)
    unpl = c2.number_input("Unplanned downtime per failure (h)", 1.0, 200.0, DEFAULTS["unplanned_downtime_hours"], 1.0)
    det_rate = c3.slider("Detection rate (see Validation tab)", 0.3, 1.0, DEFAULTS["detection_rate"], 0.05)
    price = c3.number_input("Price / machine / month (USD)", 5.0, 500.0, DEFAULTS["price_per_machine_month_usd"], 5.0)
    fx = st.number_input("PKR per USD (update to current rate)", 100.0, 1000.0, DEFAULTS["fx_pkr_per_usd"], 1.0)
    r = roi(machines=machines, failures_per_machine_year=fails, cost_per_downtime_hour_usd=cost_h, unplanned_downtime_hours=unpl, detection_rate=det_rate, price_per_machine_month_usd=price, fx_pkr_per_usd=fx)
    k = fx if cur == "PKR" else 1.0; sym = "Rs " if cur == "PKR" else "$"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross savings / yr", f'{sym}{r["gross_savings_usd"] * k:,.0f}'); m2.metric("Subscription / yr", f'{sym}{r["subscription_usd"] * k:,.0f}')
    m3.metric("Year-1 net", f'{sym}{r["year1_net_usd"] * k:,.0f}'); m4.metric("Payback (months)", r["payback_months"] if r["payback_months"] else "n/a")
    st.caption(f'Failures avoided/yr {r["failures_avoided_per_year"]} · hours saved {r["downtime_hours_saved"]} · break-even detection rate {r["break_even_detection_rate"]}')
    st.markdown("**Proposed pricing tiers (per machine / month, USD - to be validated with pilots)**")
    st.dataframe(pd.DataFrame([{"tier": t, "USD / machine / month": p} for t, p in TIERS.items()]), hide_index=True, width="stretch")
    st.markdown("**Sensitivity - year-1 net (USD)**")
    st.dataframe(pd.DataFrame(sensitivity({"machines": machines, "failures_per_machine_year": fails, "unplanned_downtime_hours": unpl, "price_per_machine_month_usd": price})), hide_index=True, width="stretch")

with tabV:
    st.caption("Honest evidence. Retrieval is measured live; detection is measured on SYNTHETIC runs with unseen seeds/speeds/noise (python -m validation.benchmark).")
    if "rag_eval" not in st.session_state:
        st.session_state["rag_eval"] = rag_eval(S.kb)
    ev = st.session_state["rag_eval"]
    st.markdown(f'#### RAG retrieval ({ev["n_questions"]} questions · {ev["n_docs"]} docs · {ev["n_chunks"]} sections)')
    st.dataframe(pd.DataFrame(ev["modes"]).T.reset_index().rename(columns={"index": "retriever"}), hide_index=True, width="stretch")
    st.caption(f'Off-topic questions correctly abstained: {ev["abstain_rate_off_topic"]:.0%} · on-topic answered: {ev["answer_rate_on_topic"]:.0%}')
    vp = Path(__file__).parent / "validation" / "results.json"
    if vp.exists():
        v = json.loads(vp.read_text())
        rows = []
        for name, key in (("Per-machine calibrated", "per_machine_calibrated"), ("Generic model, no calibration", "generic_pretrained_no_calibration")):
            x = v[key]
            rows.append({"setup": name, "detection rate": x["degradation"]["detection_rate"], "median lead (ticks before failure)": x["degradation"]["median_lead_ticks"],
                         "threshold-baseline lead": x["degradation"]["baseline_median_lead_ticks"], "false alarms /1000 ticks": x["healthy"]["ml_false_alarms_per_1000"],
                         "sensor-fault runs correct": f'{x["sensor_fault"]["system_recommends_sensor_check"]}/{x["sensor_fault"]["runs"]}',
                         "threshold raises mechanical alarm": f'{x["sensor_fault"]["baseline_raises_mechanical_alarm"]}/{x["sensor_fault"]["runs"]}'})
        st.markdown(f'#### Detection ({v["n_degradation_runs"]} degradation runs, noise 1x-2x)')
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.warning("Synthetic data. A generic model false-alarms on noisier plants, so each machine must be calibrated at commissioning. Real-plant validation is the next step.")

# ---------------- live loop ----------------
if S.running:
    S.tick()
    time.sleep(speed)
    st.rerun()
