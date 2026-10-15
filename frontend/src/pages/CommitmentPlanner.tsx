import { useState, type FormEvent } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, apiRequest } from "../api";

type TelemetryPoint = {
  step: number;
  start_minute: number;
  end_minute: number;
  baseline_grid_import_mw: number;
  grid_import_mw: number;
  delivered_reduction_mw?: number;
  battery_soc_end: number;
  workload_backlog_mwh: number;
  battery_discharge_mw: number;
};

type SimulationResult = {
  scenario_id: string;
  run_id: string;
  controller: string;
  status: string;
  execution_status: string;
  accepted_commitment_mw: number | null;
  complete_event_success: boolean | null;
  infeasibility_reason?: string | null;
  reliability: { status: string; estimate: number | null; confidence_lower_bound?: number | null; target: number | null; evidence_split?: string } | null;
  telemetry: { event_time_series: TelemetryPoint[]; final_battery_soc?: number; final_workload_backlog_mwh?: number };
  recovery?: { status: string; telemetry?: { max_grid_import_mw?: number; backlog_cleared?: boolean; soc_target_met?: boolean } };
  independent_verification: { status: string; check_count: number; failed_check_count: number; certification: boolean };
  violations: unknown[];
};

type SimulationResponse = { status: string; reliability_certified: boolean; verification: SimulationResult["independent_verification"]; result: SimulationResult };
const formatNumber = (value: number | null | undefined, digits = 2) => value == null || !Number.isFinite(value) ? "N/A" : value.toFixed(digits);

export default function CommitmentPlanner() {
  const [requestedMW, setRequestedMW] = useState(5);
  const [duration, setDuration] = useState(60);
  const [reliability, setReliability] = useState(95);
  const [batterySoC, setBatterySoC] = useState(35);
  const [seed, setSeed] = useState(20261014);
  const [calibrationScenarios, setCalibrationScenarios] = useState(1000);
  const [controller, setController] = useState("rafc_v");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setSimulation(null);
    setLoading(true);
    const scenario = {
      scenario_id: "FP-001",
      requested_reduction_mw: requestedMW,
      duration_minutes: duration,
      reliability_target: reliability / 100,
      battery_soc_percent: batterySoC,
      random_seed: seed,
      calibration_scenarios: calibrationScenarios,
      commitment_step_mw: 0.1,
      controller,
    };
    try {
      await apiRequest("/scenarios/validate", { method: "POST", body: JSON.stringify(scenario) });
      const response = await apiRequest<SimulationResponse>("/scenarios/run", { method: "POST", body: JSON.stringify(scenario) });
      if (!response.result?.telemetry) throw new Error("The API returned an incomplete result.");
      setSimulation(response.result);
      setMessage(`Run saved. Independent arithmetic checks: ${response.verification?.status ?? response.result.independent_verification.status}.`);
    } catch (reason) {
      setMessage(reason instanceof Error ? `Simulation error: ${reason.message}` : "Unable to reach the simulation API.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = simulation?.telemetry.event_time_series.map((point) => ({
    minute: point.end_minute,
    baseline: point.baseline_grid_import_mw,
    gridImport: point.grid_import_mw,
    batterySoC: point.battery_soc_end * 100,
    backlog: point.workload_backlog_mwh,
  })) ?? [];

  return <div className="planner-page">
    <p className="eyebrow">GRID FLEXIBILITY</p>
    <h1>Flexibility Commitment Planner</h1>
    <p className="subtitle">Run the FP-001 scenario through the shared Python engine and inspect the persisted result.</p>
    <section className="panel planner-panel">
      <div className="panel-header"><div><h2>Event Configuration</h2><p>RAFC-V uses calibration scenarios; the evidence is not held-out validation.</p></div></div>
      <form onSubmit={handleSubmit} className="planner-form">
        <label>Requested reduction (MW)<input type="number" min="0.1" max="20" step="0.1" value={requestedMW} onChange={(e) => setRequestedMW(Number(e.target.value))} required /></label>
        <label>Event duration<select value={duration} onChange={(e) => setDuration(Number(e.target.value))}><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={60}>60 minutes</option></select></label>
        <label>Reliability target<select value={reliability} onChange={(e) => setReliability(Number(e.target.value))}><option value={90}>90%</option><option value={95}>95%</option><option value={99}>99%</option></select></label>
        <label>Controller<select value={controller} onChange={(e) => setController(e.target.value)}><option value="rafc_v">RAFC-V</option><option value="risk_aware_mpc">Risk-aware MPC</option><option value="deterministic_mpc">Deterministic MPC</option><option value="rule_based">Rule based</option><option value="nominal">Nominal illustration</option></select></label>
        <label>Initial battery SoC (%)<input type="number" min="20" max="100" step="1" value={batterySoC} onChange={(e) => setBatterySoC(Number(e.target.value))} required /></label>
        <label>Random seed<input type="number" min="0" step="1" value={seed} onChange={(e) => setSeed(Number(e.target.value))} required /></label>
        <label>Calibration scenarios<input type="number" min="100" max="5000" step="100" value={calibrationScenarios} onChange={(e) => setCalibrationScenarios(Number(e.target.value))} required /></label>
        <button type="submit" className="primary-button" disabled={loading}>{loading ? "Running engine…" : "Validate and Run"}</button>
      </form>
      {loading && <div className="notice" role="status">Optimization may take several seconds. Please keep this page open.</div>}
      {message && <div className="notice" role="status">{message}</div>}
    </section>
    {simulation && <section className="panel planner-results">
      <div className="panel-header"><div><p className="eyebrow">SAVED ENGINE RESULT</p><h2>{simulation.scenario_id} · {simulation.controller}</h2><p>Run ID: {simulation.run_id}</p></div>
        <a className="primary-button" href={`${API_BASE}/runs/${encodeURIComponent(simulation.run_id)}/report.pdf`}>Download PDF</a></div>
      <div className="simulation-metrics">
        <Metric label="Accepted Commitment" value={`${formatNumber(simulation.accepted_commitment_mw)} MW`} />
        <Metric label="Engine Status" value={simulation.status} />
        <Metric label="Event Delivery" value={simulation.complete_event_success == null ? "Not evaluated" : simulation.complete_event_success ? "Pass" : "Shortfall"} />
        <Metric label="Calibration Evidence" value={simulation.reliability?.status ?? "Not evaluated"} />
        <Metric label="Recovery" value={simulation.recovery?.status ?? "Not returned"} />
        <Metric label="Independent Checks" value={`${simulation.independent_verification.status} · ${simulation.independent_verification.failed_check_count} failed`} />
      </div>
      {simulation.infeasibility_reason && <div className="notice" role="alert">{simulation.infeasibility_reason}</div>}
      <p className="simulation-disclaimer">Reliability estimate and lower bound describe calibration evidence. They are not held-out validation or utility certification. Independent arithmetic checks do not certify facility performance.</p>
      {chartData.length > 0 && <>
        <div className="simulation-chart"><h3>Grid Import During Event (MW)</h3><ResponsiveContainer width="100%" height={300}><LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis /><Tooltip /><Line type="monotone" dataKey="baseline" name="Baseline import" stroke="#6b7280" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="gridImport" name="Grid import" stroke="#d5a728" strokeWidth={3} dot={false} /></LineChart></ResponsiveContainer></div>
        <div className="simulation-chart"><h3>Battery SoC (%) and deferred backlog (MWh)</h3><ResponsiveContainer width="100%" height={280}><LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis yAxisId="soc" domain={[0, 100]} /><YAxis yAxisId="backlog" orientation="right" /><Tooltip /><Line yAxisId="soc" type="monotone" dataKey="batterySoC" name="Battery SoC (%)" stroke="#2563eb" strokeWidth={3} /><Line yAxisId="backlog" type="monotone" dataKey="backlog" name="Backlog (MWh)" stroke="#0f766e" strokeWidth={3} /></LineChart></ResponsiveContainer></div>
      </>}
    </section>}
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="simulation-metric"><span>{label}</span><strong>{value}</strong></div>;
}
