# MachinaGuard AI: Business Model

> **How to read this document:** every figure is an **assumption to validate in a pilot**. No market-size number is claimed. Cells marked *source needed* must be filled with a cited source before pitching.

## 1. Executive summary
MachinaGuard AI is a subscription software service that warns plants about failing machines early, explains the likely cause with cited maintenance guidance, and turns an approved diagnosis into a scheduled maintenance job. It works with sensors a plant already has, runs offline if needed, and always keeps a human in control.

## 2. The problem
- Unplanned machine stoppages are costly, and small and mid-size plants often have no reliability engineer to interpret vibration data or manuals.
- Fixed-threshold alarms catch degradation late and cannot tell a failing machine from a **failing sensor**. In our benchmark a threshold system raised a mechanical alarm in 12 of 12 sensor-fault runs; MachinaGuard recommended a sensor check in 12 of 12.
- Maintenance knowledge sits in manuals nobody reads during an incident.

## 3. Customers and buyers
| Segment | Why they would pay | First entry point |
|---|---|---|
| Textile and spinning mills | Continuous motor and spindle operation, high energy cost | Pilot on 5 to 10 critical motors and fans |
| Cement, steel, fertilizer | Very high cost per downtime hour | Fans, mill drives, compressors |
| Water and utility pumping | Remote sites, few engineers | Pump stations |

| Role | What they care about |
|---|---|
| Plant or maintenance manager (buyer) | Fewer surprise stoppages, provable savings |
| Maintenance engineer (daily user) | Clear cause, checklist, cited procedure |
| Owner or finance (approver) | Payback time, low upfront cost |

Market size: *source needed* (industry association or national statistics). Do not estimate without a source.

## 4. Value proposition
1. **Earlier warning** than a fixed threshold (median 46 vs 34 ticks before failure in the synthetic benchmark).
2. **Fewer false shutdowns** from sensor faults, because redundant sensors are compared.
3. **Trustworthy advice:** recommendations cite real documents, a Critic agent challenges them, and the system says "no evidence" instead of guessing.
4. **Safe automation:** no ticket, purchase draft or technician booking without human approval.
5. **Local fit:** English and Urdu notifications, works offline.

## 5. Revenue model (proposed, to validate)
| Tier | USD per machine per month | Includes |
|---|---|---|
| Starter (1 to 10 machines) | 55 | Self-serve, shift reports, drafted alerts |
| Plant (11 to 50 machines) | 40 | Onboarding, maintenance-system hooks |
| Enterprise (50+ machines) | 28 | On-premise option, SLA |

- One-time setup and calibration: about **$1,500 per plant** (assumption).
- Hardware: use the plant's existing sensors or PLC data first; low-cost sensor kits as an optional resale.

## 6. Unit economics
Live calculator: **Business & ROI** tab. Default scenario:

| Input | Value |
|---|---|
| Machines | 20 |
| Failures per machine per year | 0.5 |
| Unplanned downtime per failure | 16 h |
| Cost per downtime hour | $800 |
| Detection rate / avoidable share | 80% / 70% |
| Price | $40 per machine per month (Plant tier) |

| Output | Value |
|---|---|
| Failures avoided per year | 5.6 |
| Downtime hours saved | 75.6 |
| Gross savings per year | ≈ $60,480 |
| Subscription per year | $9,600 |
| Year-1 net (after $1,500 setup) | ≈ $49,380 |
| Break-even detection rate | ≈ 13% |

The sale does not depend on perfect AI: even a low detection rate covers the subscription under these assumptions. The sensitivity table in the app shows the downside cases (for example $300 per hour at 50% detection yields only about $3,000 net).

## 7. Go-to-market
1. **Free 30-day pilot** on 5 machines using the plant's existing data.
2. **Pilot success metrics:** warning lead time before real faults, false alarms per week, avoided downtime hours, share of work orders accepted by engineers.
3. **Convert** with an ROI report built from the pilot's real data.
4. **Expand** through system integrators and maintenance contractors, and build credibility through industry associations.

## 8. Competitive position
Global condition-monitoring vendors exist and are typically enterprise-oriented. *Verify current pricing and language support before claiming a gap.* MachinaGuard's intended edge is the combination of per-machine calibration, a challenge step, cited advice, approval-gated automation, local-language workflow and low cost for smaller plants.

## 9. Moat (to build)
- Plant-specific calibrated baselines.
- Feedback loop: every approved or rejected work order improves the rules.
- Accumulated, plant-approved maintenance document library.
- Local-language workflow and relationships with integrators.

## 10. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Validated on synthetic data only | First roadmap item: public bearing dataset, then a pilot plant |
| Generic model false-alarms on noisy plants (194 per 1,000 ticks) | Mandatory per-machine calibration (2 per 1,000 after) |
| AI provider outage or quota | Automatic fallback to a second provider, then offline logic |
| Customers distrust automation | Human approval gate, audit log, every action labelled |
| Data connectivity at the plant | Offline mode keeps core detection and workflow running |

## 11. Assumptions register
| Assumption | Current value | Source |
|---|---|---|
| Cost per downtime hour | $800 | *source needed* |
| Failures per machine per year | 0.5 | *source needed* |
| Unplanned downtime per failure | 16 h | *source needed* |
| Detection rate in real plants | 80% | to be measured in pilot |
| Share of detected failures avoidable | 70% | to be measured in pilot |
| Price tiers | 55 / 40 / 28 USD | to be tested with pilot customers |
| FX rate | 280 PKR per USD | update to the current rate |

## 12. 12-month plan (targets, not forecasts)
| Quarter | Goal |
|---|---|
| Q1 | Pilots and real-data validation |
| Q2 | Maintenance-system and WhatsApp Business integration |
| Q3 | First paid conversions |
| Q4 | Multi-plant dashboard |