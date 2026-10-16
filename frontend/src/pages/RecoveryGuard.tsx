import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RecordedRun } from "./CommitmentPlanner";

const num = (value: number | undefined, digits = 3) => value == null || !Number.isFinite(value) ? "Unavailable" : value.toFixed(digits);

export default function RecoveryGuard({ run, onPlan }: {run: RecordedRun | null; onPlan: () => void}) {
  if (!run) return <section className="panel"><h1>RecoveryGuard</h1><p>No run is selected.</p><button className="primary-button" type="button" onClick={onPlan}>Open Commitment Planner</button></section>;
  const recovery = run.result.recovery;
  if (!recovery) return <section className="panel"><h1>RecoveryGuard</h1><p>No RecoveryGuard evidence was returned for this run.</p></section>;
  const config = run.config.recovery;
  const rows = recovery.telemetry.recovery_time_series ?? [];
  const atSocDeadline = rows.filter((row) => row.end_minute <= config.target_minute).at(-1);
  const atWorkDeadline = rows.filter((row) => row.end_minute <= config.clear_deferred_work_by_minute).at(-1);
  const target = atSocDeadline ? atSocDeadline.battery_soc_end + 1e-6 >= config.target_soc : null;
  const cleared = atWorkDeadline ? atWorkDeadline.workload_backlog_end_mwh <= 1e-6 : null;
  const final = rows.at(-1);
  const peak = rows.length ? Math.max(...rows.map((row) => row.grid_import_mw)) : undefined;
  const data = rows.map((row) => ({...row, minute: row.end_minute, socPercent: row.battery_soc_end * 100,
    socTarget: config.target_soc * 100, ceiling: config.grid_import_ceiling_mw}));
  return <div className="planner-page"><p className="eyebrow">JOINT BATTERY AND WORKLOAD RECOVERY</p><h1>RecoveryGuard</h1>
    <p className="subtitle">{run.result.run_id} · {recovery.controller_version ?? "Version unavailable"} · {recovery.status}</p>
    {!run.result.complete_event_success && <div className="notice" role="alert">The event did not complete successfully. This recovery output is a conditional plan for the returned state and does not establish successful event execution.</div>}
    {recovery.infeasibility_reason && <div className="notice" role="alert">Recovery infeasible: {recovery.infeasibility_reason}</div>}
    <section className="panel planner-results"><div className="simulation-metrics">
      <Metric label="Recovery status" value={recovery.status} />
      <Metric label="Final battery SoC" value={`${num(final ? final.battery_soc_end * 100 : undefined)}%`} />
      <Metric label="Final backlog" value={`${num(final?.workload_backlog_end_mwh)} MWh`} />
      <Metric label="Maximum recovery import" value={`${num(peak)} MW`} />
      <Metric label={`SoC target at minute ${config.target_minute}`} value={target == null ? "Unavailable" : target ? "Met" : "Failed"} />
      <Metric label={`Work deadline at minute ${config.clear_deferred_work_by_minute}`} value={cleared == null ? "Unavailable" : cleared ? "Cleared" : "Missed"} />
    </div>
    <p className="simulation-disclaimer">The {config.nominal_base_demand_mw} MW recovery base is an explicit planning assumption. Battery charging and restored compute share one {config.grid_import_ceiling_mw} MW import ceiling. The plots show the existing engine's deterministic recovery schedule.</p>
    {data.length > 0 && <>
      <div className="simulation-chart"><h2>Recovery import and shared ceiling (MW)</h2><ResponsiveContainer width="100%" height={280}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis /><Tooltip /><Legend />
        <Line isAnimationActive={false} dataKey="grid_import_mw" name="Grid import" stroke="#0f766e" dot={false} /><Line isAnimationActive={false} dataKey="ceiling" name="Ceiling" stroke="#b45309" strokeDasharray="5 5" dot={false} />
        <Line isAnimationActive={false} dataKey="battery_charge_mw" name="Battery charging" stroke="#2563eb" dot={false} /><Line isAnimationActive={false} dataKey="workload_recovery_mw" name="Restored compute" stroke="#a16207" dot={false} />
      </LineChart></ResponsiveContainer></div>
      <div className="simulation-chart"><h2>Battery recharge and SoC target (%)</h2><ResponsiveContainer width="100%" height={260}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis domain={[0,100]} /><Tooltip /><Legend /><Line isAnimationActive={false} dataKey="socPercent" name="SoC" stroke="#2563eb" dot={false} /><Line isAnimationActive={false} dataKey="socTarget" name="Target" stroke="#64748b" dot={false} /></LineChart></ResponsiveContainer></div>
      <div className="simulation-chart"><h2>Deferred workload clearance (MWh)</h2><ResponsiveContainer width="100%" height={260}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis /><Tooltip /><Line isAnimationActive={false} dataKey="workload_backlog_end_mwh" name="Remaining backlog" stroke="#0f766e" dot={false} /></LineChart></ResponsiveContainer></div>
    </>}
    <h2>Recovery interval evidence</h2><p>{rows.length} of {config.horizon_minutes / config.interval_minutes} planned intervals returned.</p>
    <div className="telemetry-table"><table><thead><tr><th>Minutes</th><th>Charge MW</th><th>Restored compute MW</th><th>Grid MW</th><th>SoC %</th><th>Backlog MWh</th><th>Ceiling check</th></tr></thead><tbody>{rows.map((row) => <tr key={row.step} data-testid="recovery-interval-row"><td>{row.start_minute}–{row.end_minute}</td><td>{num(row.battery_charge_mw)}</td><td>{num(row.workload_recovery_mw)}</td><td>{num(row.grid_import_mw)}</td><td>{num(row.battery_soc_end * 100)}</td><td>{num(row.workload_backlog_end_mwh)}</td><td>{row.grid_import_mw <= config.grid_import_ceiling_mw + 1e-6 ? "Within ceiling" : "Violation"}</td></tr>)}</tbody></table></div>
    {recovery.violations?.length > 0 && <pre role="alert">{JSON.stringify(recovery.violations, null, 2)}</pre>}
    </section></div>;
}

function Metric({label, value}: {label: string; value: string}) {return <div className="simulation-metric"><span>{label}</span><strong>{value}</strong></div>;}
