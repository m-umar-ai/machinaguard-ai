# Mapping to the Pak Angels Cohort 11 requirement
"Apply **two or more** of: Generative AI, Agentic AI, AI Workflows, Multi-Agent Systems, AI-powered Business Process Automation." MachinaGuard covers **all five**:

| Required skill | Where it lives | How to show it in 30 s |
|---|---|---|
| **Multi-Agent Systems** | 9-stage pipeline: Anomaly, Diagnosis, RAG, Investigator, Risk, **Critic**, Decision, Workflow agents with typed hand-offs and per-agent failure isolation | Demo Mode timeline; kill-switch test (`test_agent_failure_is_survived`) |
| **Agentic AI** | `agents/agent_loop.py`: tool-using loop (8 tools, whitelist, step budget, JSON recovery) driven by an LLM, rule-planner fallback; draft-only tools | **🤖 Agent Trace** tab: every tool call + observation |
| **Generative AI** | Grounded RAG answers with verified citations, "Ask the Machine", EN/UR shift reports & WhatsApp alerts, LLM adversarial critic | **💬 Ask** and **📝 Reports** tabs |
| **AI Workflows** | Retrieval → investigation → critique → decision → approval gate, all orchestrated and audited | Decision trace panel |
| **Business Process Automation** | `workflows/process_engine.py`: approval → parts/stock check → draft purchase request → technician match → SLA scheduling → bilingual notifications, full audit log | **✅ Approval & Process** tab after APPROVE |
| Business model | `BUSINESS_MODEL.md` + live ROI/PKR calculator + pricing tiers + sensitivity | **💼 Business & ROI** tab |
| Evidence | Retrieval eval (30 questions, abstention) + detection benchmark vs threshold baseline | **📊 Validation** tab |

## 5-minute demo order
1. 20 s problem + "AI operations system, not a chatbot". 2. DEMO MODE: degradation → anomaly. 3. **Agent Trace** (tools called). 4. Evidence with citations. 5. Critic challenges. 6. APPROVE → **process automation** (parts missing → draft purchase request). 7. Urdu WhatsApp alert. 8. RESET → INJECT SENSOR FAULT → system says verify sensor (threshold system would shut down). 9. ROI tab (PKR). 10. Validation tab: honest limits.

## Rules check before submitting
- Confirm the hackathon allows work started before Friday 9 PM; if the rules say "built during the hackathon", declare the existing base and show what you built in the window.
- Team of 4–6, leader registers before Saturday 12:00 noon PKT, keep the confirmation/edit link.
