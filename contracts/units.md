# Units

Power is MW; energy is MWh; workload is MW-equivalent-hours; time is minutes; SoC is a fraction. Facility/battery powers are AC-side at the grid boundary. Battery SoC tracks DC energy: delta SoC = (eta_charge*P_charge - P_discharge/eta_discharge)*dt_hours/capacity. Positive grid import means import; charging increases and discharging decreases it. Feasibility tolerance is 1e-9.
