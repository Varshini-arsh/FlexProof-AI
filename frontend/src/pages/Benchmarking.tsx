import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type BenchmarkRow = {
  controller: string; commitment_mw: number; event_successes: number; heldout_count: number;
  event_success_probability: number; event_wilson_interval: [number, number];
  event_and_recovery_success_probability: number; joint_wilson_interval: [number, number];
  mean_delivered_mw: number | null; mean_max_shortfall_mw: number | null;
  battery_reserve_violation_scenarios: number; workload_deadline_miss_scenarios: number;
  recovery_successes: number; recovery_feasibility_probability: number;
  mean_rebound_peak_mw: number | null; max_rebound_peak_mw: number | null;
  mean_event_solver_runtime_seconds: number | null; schedule_setup_solver_runtime_seconds: number | null;
  solver_failure_scenarios: number; failure_categories: Record<string, number>;
};
type BenchmarkArtifact = {
  status: string; reason: string; summary?: {
    experiment_id: string; scenario_id: string; protocol: {heldout_sample_count: number; heldout_seed_start: number;
      calibration_sample_count: number; calibration_seed_start: number; confidence_level: number;
      heldout_data_used_for_commitment_selection: boolean; wall_runtime_seconds: number};
    commitment_calibration: Record<string, {accepted_commitment_mw: number}>;
    results: BenchmarkRow[];
    paired_tests: Record<string, {event_mcnemar: {p_value: number; holm_adjusted_p_value: number; discordant_pairs: number}}>
  }
};

const pct = (value: number | null | undefined) => value == null ? "Unavailable" : `${(value * 100).toFixed(2)}%`;
const num = (value: number | null | undefined, digits = 3) => value == null ? "Unavailable" : value.toFixed(digits);

export default function Benchmarking() {
  const [artifact, setArtifact] = useState<BenchmarkArtifact | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { apiRequest<BenchmarkArtifact>("/benchmarks/closed-loop").then(setArtifact)
    .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Benchmark API unavailable")); }, []);
  if (error) return <section className="panel"><h1>Benchmarking</h1><p role="alert">Benchmark data unavailable: {error}</p></section>;
  if (!artifact) return <section className="panel"><h1>Benchmarking</h1><p>Loading recorded benchmark artifact…</p></section>;
  if (!artifact.summary || artifact.status === "unavailable" || artifact.status === "invalid_artifact" || artifact.status === "integrity_mismatch")
    return <section className="panel"><h1>Benchmarking</h1><p role="status">Benchmark metrics unavailable: {artifact.reason}</p></section>;
  const summary = artifact.summary;
  const rows = summary.results;
  const label = (controller: string) => controller === "fixed_horizon" ? "Fixed horizon" : controller === "rolling_risk_aware_mpc" ? "Rolling risk-aware MPC" : "RAFC-V";
  const chartRows = rows.map((row) => ({controller: label(row.controller), event: row.event_success_probability * 100,
    eventAndRecovery: row.event_and_recovery_success_probability * 100}));
  const rollingTest = summary.paired_tests.rolling_risk_aware_mpc_vs_rolling_rafc_v?.event_mcnemar;
  return <div className="planner-page"><p className="eyebrow">HELD-OUT PAIRED CONTROLLER EVALUATION</p><h1>Benchmarking</h1>
    <p className="subtitle">{summary.experiment_id} · {summary.protocol.heldout_sample_count.toLocaleString()} held-out scenarios · {artifact.status}</p>
    <div className="notice" role="status">{artifact.reason} Commitments were selected using {summary.protocol.calibration_sample_count.toLocaleString()} separate calibration scenarios. Held-out data used for selection: {String(summary.protocol.heldout_data_used_for_commitment_selection)}.</div>
    <section className="panel planner-results">
      <h2>Measured controller outcomes</h2>
      <div className="simulation-chart"><ResponsiveContainer width="100%" height={320}><BarChart data={chartRows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="controller" /><YAxis domain={[0,100]} unit="%" /><Tooltip /><Legend />
        <Bar dataKey="event" name="Complete event success (%)" fill="#287c82" /><Bar dataKey="eventAndRecovery" name="Event and recovery success (%)" fill="#4c7c52" /><ReferenceLine y={95} stroke="#b45309" strokeDasharray="5 5" label="95% target" /></BarChart></ResponsiveContainer></div>
      <div className="telemetry-table"><table><thead><tr><th>Controller</th><th>Commit MW</th><th>Event success (95% Wilson CI)</th><th>Event + recovery</th><th>Mean delivered MW</th><th>Mean max shortfall MW</th><th>Reserve violations</th><th>Deadline misses</th><th>Recovery feasible</th><th>Rebound peak mean / max MW</th><th>Event solver sec</th><th>Solver failures</th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.controller}><td>{row.controller}</td><td>{num(row.commitment_mw, 2)}</td><td>{row.event_successes}/{row.heldout_count} ({pct(row.event_success_probability)}; {pct(row.event_wilson_interval[0])}–{pct(row.event_wilson_interval[1])})</td><td>{pct(row.event_and_recovery_success_probability)} ({pct(row.joint_wilson_interval[0])}–{pct(row.joint_wilson_interval[1])})</td><td>{num(row.mean_delivered_mw)}</td><td>{num(row.mean_max_shortfall_mw)}</td><td>{row.battery_reserve_violation_scenarios}</td><td>{row.workload_deadline_miss_scenarios}</td><td>{row.recovery_successes}/{row.heldout_count}</td><td>{num(row.mean_rebound_peak_mw)} / {num(row.max_rebound_peak_mw)}</td><td>{row.mean_event_solver_runtime_seconds == null ? `setup ${num(row.schedule_setup_solver_runtime_seconds)} s (one-time)` : num(row.mean_event_solver_runtime_seconds)}</td><td>{row.solver_failure_scenarios}</td></tr>)}</tbody></table></div>
      <h2>Rolling risk-aware MPC vs RAFC-V</h2>
      <p>Paired exact McNemar test: p={rollingTest?.p_value ?? "Unavailable"}; Holm-adjusted p={rollingTest?.holm_adjusted_p_value ?? "Unavailable"}; discordant event outcomes={rollingTest?.discordant_pairs ?? "Unavailable"}. A zero difference does not establish superiority.</p>
      <p className="simulation-disclaimer">Modeled uncertainty assumptions only; not measured facility performance. Fixed-horizon uses a frozen nominal schedule; rolling controllers receive interval observations. Runtime fields have different aggregation as labeled. Full raw files are checksum-referenced separately; this dashboard uses the reproducibly verified summary.</p>
    </section></div>;
}
