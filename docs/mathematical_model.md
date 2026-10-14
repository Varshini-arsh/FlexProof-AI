# Mathematical model: foundation

All facility powers are AC-side MW. At each interval, grid import is P_grid = P_critical + P_fixed + P_flexible + P_charge - P_discharge. The baseline FP-001 import is 12+4+4 = 20 MW. Flexible compute is bounded between zero and 4 MW; critical and fixed demand cannot be curtailed by this model.

Battery stored energy is DC-side. For interval duration dt hours, SoC_next = SoC + (eta_c P_charge - P_discharge/eta_d) dt / E_capacity. Enforce configured SoC bounds, inverter limits, nonnegative powers, and charge/discharge exclusivity. FP-001 usable energy above the 20% reserve is 1.5 MWh DC / 1.425 MWh AC. Thus 3 MW for an hour is infeasible.

Work units are MW-equivalent-hours, an energy proxy. This linear abstraction does not model GPU performance, job parallelism, or cooling transients.
