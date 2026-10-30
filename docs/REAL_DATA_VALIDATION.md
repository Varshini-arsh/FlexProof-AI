# FlexProof AI: real-data validation (CAISO 2024 + Azure LLM inference)

## Why

All earlier results use modeled FP-001 disturbances. This experiment replaces three of them with public data:

| Modeled before | Real data now |
|---|---|
| One 60-minute event at an arbitrary time | 27 real CAISO 2024 grid stress events, each with its real start time and duration |
| Meter noise of about 0.02 MW is the only error in the measured cut | AI load drift during the event, from the Azure LLM inference trace |
| Fixed 17 MW recovery base | Recovery base from real AI load in the 4 hours after each event |

Battery derating, urgent reclaim and initial SoC error keep the modeled FP-001 assumptions.

## Data

- **Grid events.** CAISO OASIS real-time 15-minute LMP at the SP15 trading hub, all of 2024. An event is a run of intervals at or above $200/MWh (about the top 0.5% of intervals), with one-interval dips merged and duration capped at the 300-minute deferral limit. This gives 27 events: 21 start between 16:30 and 19:45 Pacific, 6 start between midnight and 07:00, and durations range from 15 to 300 minutes. ERCOT was the first choice but its public MIS endpoint returned HTTP 403 from the development network.
- **AI load.** Azure LLM inference trace 2024 (code and conversation services, May 10-18 2024, CC-BY 4.0; Stojkovic et al., "DynamoLLM", HPCA 2025). Token throughput is binned to 5 minutes, each service is normalized by its own 99th percentile, and the facility utilization is the mean of the services present.

## Method

- **Power mapping (assumption).** Critical inference power = 12 MW x (0.4 + 0.6 x utilization). The 0.4 idle floor reflects that GPU servers draw substantial power at low load. Timestamps are UTC and the facility is placed in Pacific time.
- **Baseline drift.** Demand response is measured against a baseline set before the event. Here the baseline is the mean critical power over the preceding 60 minutes, and drift is the maximum critical power during the event minus that baseline. Positive drift reduces the measured cut. Samples use every trace day, with start times within +/-60 minutes of the real event's local start.
- **Held-out split.** Commitments are calibrated with drift from May 9-14 (local dates) and tested on drift from the unseen May 15-18.
- **Per event.** 1,000 calibration scenarios and 200 held-out paired scenarios. Both rolling arms use dispatch v2. RAFC-V and risk-aware MPC differ only in the recovery screen, as before.
- **Synthetic-only check.** The original controller, calibrated with modeled disturbances only (no drift), is checked analytically against the held-out real drift. It shows what the purely modeled system would have promised.

Command:

```powershell
python -m pip install -e ".[realdata]"
python -m realdata.fetch --year 2024
python -m evaluation.run_real_data --calibration-scenarios 1000 --test-scenarios 200
```

The run took about 2 hours on 6 worker processes; the 5-hour events dominate. Aggregates are in `results/summaries/real-data-caiso2024-summary.json` and per-event rows in `results/summaries/real-data-caiso2024-events.csv`.

## Results

### Headline

| | Mean commitment | Mean held-out success | Events meeting 95% | Events below 80% |
|---|---:|---:|---:|---:|
| Synthetic-only (modeled assumptions) | 4.67 MW | 75.1% | 17 / 27 | 9 |
| Rolling risk-aware MPC (real-data calibrated) | 4.33 MW | 92.2% | 19 / 27 | 3 |
| Rolling RAFC-V (real-data calibrated) | 4.23 MW | 95.8% | 19 / 27 | 2 |

Duration-weighted success (longer events count more): RAFC-V 89.2%, MPC 74.7%. Total RAFC-V committed energy is 96.4 MWh across the 27 events. At the mean real-time price during each event this is about $36,700 of indicative energy value for one 20 MW facility; that is not a program payment.

### By event type

| Event type | Events | Synthetic-only commitment / success | RAFC-V commitment / success |
|---|---:|---:|---:|
| Evening, under 120 min | 17 | 4.96 MW / 95.9% | 4.92 MW / 98.3% |
| Morning (before noon) | 6 | 4.47 MW / 54.2% | 3.42 MW / 99.0% |
| Long (120 min or more) | 6 | 3.63 MW / 13.3% | 2.10 MW / 86.0% |

(Two long events also start in the morning, so the last two rows overlap.)

### Findings

1. **AI load drift is the dominant real-world risk, and the modeled system ignores it.** For a one-hour event the median drift is +1.44 MW at 06:00 Pacific (p95 +1.85 MW), against modeled meter noise of 0.02 MW. The synthetic-only controller over-promises on morning and long events. Examples: Jan 8 06:30 (60 min), 4.9 MW promised and 18.5% delivered; Jan 13 05:15 (135 min), 4.2 MW promised and 0% delivered. Real-data calibration lowers those promises to 3.1 MW and 0.9 MW, and both succeed in 100% of held-out scenarios.
2. **Most real stress events are easy for an AI datacentre.** 17 of 27 events are short evening events, when this AI load is near its daily low. There RAFC-V commits nearly the full 5 MW (mean 4.92 MW) with 98.3% success.
3. **RAFC-V beats risk-aware MPC on a real event where recovery binds.** The commitments differ on the two 5-hour January events. On Jan 16 00:00 the recovery base is 16.5 MW, because AI load rises during the morning recovery window. MPC promises 2.9 MW and succeeds in 0 of 200 held-out scenarios; RAFC-V promises 1.5 MW and succeeds in 188 of 200 (94.0%; exact McNemar p = 5e-57). On Jan 15 16:30 the difference is not significant (74.5% vs 72.0%, p = 0.06). This is the first case where RAFC-V's recovery screen helps without an artificially lowered grid ceiling. It is one event, so it shows the mechanism, not a general advantage.
4. **The 95% target is not met on 8 of 27 events, including all 5 events of 165 minutes or more.** Held-out drift is larger than calibration drift (mean p95 1.15 MW vs 0.78 MW), so commitments calibrated on six days are too optimistic for the next four. With about one week of AI load data, this distribution shift is the main honest limit of the result. Long events also stack more drift risk.

### Fixed-horizon comparator

The fixed schedule averages 15.7% success. It is not a fair comparator here: it plans once with the modeled 99% meter margin, never learns about drift, and the margin is capped at the 5 MW request when the commitment is the full request. The repository previously withdrew an unfair fixed-horizon comparison, so this number is reported only for completeness and is not evidence for RAFC-V.

## Limitations

- Price spikes are a proxy for grid stress, not actual demand-response dispatch instructions.
- The Azure trace covers about one week in May 2024. It is reused by time of day for events across all of 2024, so seasonal and weekly AI load changes are not represented.
- Token throughput is a proxy for GPU power. The utilization-to-MW mapping (12 MW rated, 0.4 idle floor) is an assumption and has not been varied in this run.
- The baseline rule (prior 60-minute mean) is one common choice; real programs use others.
- Battery derating, urgent reclaim and initial SoC error remain modeled assumptions.
- 200 held-out scenarios per event give about +/-3 percentage points of sampling error near 95%.

## Next steps

1. Longer AI load data (months, not a week) to reduce calibration-to-test shift; measured facility power if a partner provides it.
2. A conservative calibration option (for example a drift safety quantile) so long events meet the 95% target.
3. Real demand-response dispatch records (CAISO ELRP or utility DR program events) instead of price spikes.
4. Sensitivity to the idle floor and the baseline rule.
5. A risk-aware MPC that also screens recovery, as the fairest comparator for finding 3.
