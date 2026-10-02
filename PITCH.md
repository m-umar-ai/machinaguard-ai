# MachinaGuard AI: Pitch and Demo Script

## One sentence
An AI operations system that detects machine failures early, explains why with cited manuals, challenges its own diagnosis, and automates maintenance after a human approves. **Not a chatbot.**

## 30 seconds
Factories lose money when a failing machine is caught late, or when a faulty sensor triggers a needless shutdown. MachinaGuard watches machine data with ML, lets specialised agents investigate and retrieve maintenance guidance, has a Critic agent challenge the diagnosis, and asks a person to approve before it creates the maintenance workflow.

## 1 minute
Add: it separates observed data, AI interpretation and recommendation. It distrusts a single signal: when two redundant sensors disagree, confidence drops and it recommends checking the sensor. It never acts without approval, and it still works offline.

## 5-minute demo order
| Min | Do this | Say this |
|---|---|---|
| 0:00 | Show the Command Center | "Machine M-04, healthy. Problem: late warnings and false shutdowns." |
| 0:30 | Click **🎬 DEMO MODE** (set seconds per tick to about 2) | "Degradation starts: vibration, then temperature, then energy." |
| 1:15 | Open **🤖 Agent Trace** | "The agent chooses tools and reads the results. Every call is visible." |
| 1:45 | Open **📚 Evidence (RAG)** | "Real passages from maintenance documents, with citations." |
| 2:15 | Open **🧠 Decision & Critic** | "A separate Critic challenges the diagnosis and lowers confidence." |
| 2:45 | Open **✅ Approval & Process**, approve | "Only now does the workflow run: parts check, purchase draft, technician, SLA, audit log. All simulated." |
| 3:30 | Open **📝 Reports EN/اردو** | "English and Urdu alerts for the shift team." |
| 3:50 | **RESET**, start, **⚠️ INJECT SENSOR FAULT** | "A threshold alarm would shut the line down. MachinaGuard says: verify the sensor first." |
| 4:20 | Open **💼 Business & ROI** | "20 machines: about $60k savings a year against $9.6k subscription. Break-even detection is about 13%." |
| 4:45 | Open **📊 Validation** | "Honest limits: synthetic data today, pilot validation next." |

## Why multi-agent, why RAG
- **Multi-agent:** each stage has its own inputs and outputs and can fail independently. The Critic is only useful as a separate, adversarial role.
- **RAG:** recommendations must cite real procedures, not model memory.

## Likely questions and honest answers
| Question | Answer |
|---|---|
| Is the ML real? | Yes. An Isolation Forest trained on healthy data decides the status. Per-sensor z-scores only explain it. |
| Is the data real? | No, it is synthetic. The benchmark shows robustness to seeds and noise, not real-plant performance. The next step is a public bearing dataset and a pilot. |
| Are the dollar figures real? | No. They are labelled assumptions that a pilot would replace. |
| What if the AI is wrong? | It reports confidence as a hypothesis, the Critic challenges it, and a human must approve any action. |
| What if the AI provider is down or rate-limited? | It tries a second provider, then falls back to offline logic. Every core feature still works. |
| Can it act on its own? | No. Without approval the workflow returns nothing. This is covered by an automated test. |
| Who pays and why? | Plants with costly downtime and few reliability engineers. See the business model. |

