# Mathematical model

All facility powers are AC-side MW. At each interval, grid import is P_grid = P_critical + P_fixed + P_flexible + P_charge - P_discharge. The baseline FP-001 import is 12+4+4 = 20 MW. Flexible compute is bounded between zero and 4 MW; critical and fixed demand cannot be curtailed in this model.

Battery stored energy is DC-side. For interval duration dt hours, SoC_next = SoC + (eta_c P_charge - P_discharge/eta_d) dt / E_capacity. Enforce configured SoC bounds, inverter limits, nonnegative powers, and charge/discharge exclusivity. FP-001 usable energy above the 20% reserve is 1.5 MWh DC / 1.425 MWh AC. Thus 3 MW for an hour is infeasible.

Deferrable work is represented in MW-equivalent-hours. Job backlog evolves as W_next=max(0, W_current-P_served*dt). The scheduler uses earliest-deadline-first and never discards remaining work. The time model is discrete: a job is first eligible at the first interval start at or after arrival; a service interval is skipped if it would extend beyond the job deadline. These conservative rules avoid crediting service before arrival or after a deadline. This linear abstraction does not model GPU performance, job parallelism, or cooling transients.

For event interval k, delivered reduction is baseline import minus measured grid import. Complete-event delivery succeeds only when every interval meets the accepted commitment and there are no modeled safety violations. The nominal FP-001 trace is a deterministic example only; it does not provide statistical evidence for the 95% target.