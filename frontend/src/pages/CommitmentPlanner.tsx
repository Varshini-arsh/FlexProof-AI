
import { useState, type FormEvent } from "react";
import { apiRequest } from "../api";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type TelemetryPoint = {
  step: number;
  start_minute: number;
  end_minute: number;
  baseline_grid_import_mw: number;
  grid_import_mw: number;
  battery_soc_end: number;
  workload_backlog_mwh: number;
  battery_discharge_mw: number;
  battery_charge_mw?: number;
  flexible_compute_mw?: number;
  delivered_reduction_mw?: number;
  success?: boolean;
};

export type SimulationResult = {
  controller: string;
  controller_version: string;
  scenario_id: string;
  run_id: string;
  status: string;
  execution_status: string;
  accepted_commitment_mw: number | null;
  complete_event_success: boolean | null;
  infeasibility_reason?: string | null;
  reliability: {
    status: string;
    estimate: number | null;
    target: number | null;
    confidence_lower_bound?: number | null;
    sample_count?: number;
    evidence_split?: string;
  } | null;
  telemetry: {
    event_time_series: TelemetryPoint[];
    final_battery_soc?: number;
    final_workload_backlog_mwh?: number;
  };
  violations: Array<{ type?: string; minute?: number; reason?: string }>;
  recovery?: RecoveryResult;
};

export type RecoveryPoint = {
  step: number; start_minute: number; end_minute: number; grid_import_mw: number;
  base_demand_mw: number; workload_recovery_mw: number; battery_charge_mw: number;
  battery_soc_start: number; battery_soc_end: number;
  workload_backlog_start_mwh: number; workload_backlog_end_mwh: number;
};
export type RecoveryResult = {
  status: string; controller_version?: string; infeasibility_reason?: string | null;
  telemetry: { recovery_time_series: RecoveryPoint[]; initial_backlog_mwh?: number; initial_battery_soc?: number;
    final_battery_soc?: number; final_workload_backlog_mwh?: number; grid_import_ceiling_mw?: number };
  violations: Array<{type?: string; reason?: string}>;
};
export type ScenarioConfiguration = {
  recovery: { horizon_minutes: number; interval_minutes: number; nominal_base_demand_mw: number;
    grid_import_ceiling_mw: number; target_soc: number; target_minute: number; clear_deferred_work_by_minute: number };
  [key: string]: unknown;
};

export type ScenarioInput = {
  scenario_id: string; requested_reduction_mw: number; duration_minutes: number;
  reliability_target: number; battery_soc_percent: number;
  controller: string; random_seed: number; calibration_scenarios: number;
  commitment_step_mw: number; recovery_grid_ceiling_mw: number;
};
export type RecordedRun = { request: ScenarioInput; config: ScenarioConfiguration; result: SimulationResult };

type SimulationResponse = {
  scenario: ScenarioConfiguration;
  status: string;
  simulation_type: string;
  reliability_certified: boolean;
  result: SimulationResult;
};

type Assessment = {
  requested_reduction_mw: number; recommended_commitment_mw: number; reliability_target: number;
  feasibility_status: string; explanation: string; controller_version: string;
  calibration: { estimate: number | null; simultaneous_lower_bound: number | null; sample_count: number; wilson_interval: number[] | null };
  held_out_validation: { status: string; reason: string };
};

const formatNumber = (value: number | null | undefined, digits = 2) =>
  value != null && Number.isFinite(value) ? value.toFixed(digits) : "N/A";

export default function CommitmentPlanner({ initialRun, onRun }: {
  initialRun?: RecordedRun | null; onRun?: (run: RecordedRun | null) => void;
}) {
  const [requestedMW, setRequestedMW] = useState(initialRun?.request.requested_reduction_mw ?? 5);
  const [duration, setDuration] = useState(initialRun?.request.duration_minutes ?? 60);
  const [reliability, setReliability] = useState((initialRun?.request.reliability_target ?? 0.95) * 100);
  const [batterySoC, setBatterySoC] = useState(initialRun?.request.battery_soc_percent ?? 35);
  const [controller, setController] = useState(initialRun?.request.controller ?? "nominal");
  const [seed, setSeed] = useState(initialRun?.request.random_seed ?? 20261014);
  const [calibrationScenarios, setCalibrationScenarios] = useState(initialRun?.request.calibration_scenarios ?? 1000);
  const [recoveryCeiling, setRecoveryCeiling] = useState(initialRun?.request.recovery_grid_ceiling_mw ?? 20);
  const [assessment, setAssessment] = useState<Assessment | null>(null);

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [simulation, setSimulation] = useState<SimulationResult | null>(initialRun?.result ?? null);

  const requestData = (): ScenarioInput => ({ scenario_id: "FP-001", requested_reduction_mw: requestedMW,
    duration_minutes: duration, reliability_target: reliability / 100, battery_soc_percent: batterySoC,
    controller, random_seed: seed, calibration_scenarios: calibrationScenarios, commitment_step_mw: 0.1,
    recovery_grid_ceiling_mw: recoveryCeiling });

  async function handleAssessment() {
    setLoading(true); setMessage(""); setAssessment(null);
    try { setAssessment(await apiRequest<Assessment>("/commitments/evaluate", { method: "POST", body: JSON.stringify(requestData()) })); }
    catch (error) { setMessage(`Commitment assessment error: ${error instanceof Error ? error.message : "API unavailable"}`); }
    finally { setLoading(false); }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setMessage("");
    setSimulation(null);
    onRun?.(null);

    if (requestedMW <= 0 || requestedMW > 20) {
      setMessage("Requested reduction must be greater than 0 and at most 20 MW.");
      return;
    }

    if (duration < 15 || duration > 60) {
      setMessage("Event duration must be between 15 and 60 minutes.");
      return;
    }

    if (batterySoC < 20 || batterySoC > 100) {
      setMessage("Battery SoC must be between 20% and 100%.");
      return;
    }

    const scenario = requestData();

    setLoading(true);

    try {
      const data = await apiRequest<SimulationResponse>("/scenarios/run", {
        method: "POST", body: JSON.stringify(scenario),
      });

      if (!data.result || !data.result.telemetry) {
        throw new Error("The backend returned an incomplete simulation result.");
      }

      setSimulation(data.result);
      onRun?.({ request: scenario, config: data.scenario, result: data.result });
      setMessage(data.result.status === "solver_error" ? "The optimizer failed. No fallback schedule was used." : data.result.status === "infeasible"
        ? "The nominal dispatch is infeasible. Inspect the returned constraints and partial evidence below."
        : data.result.accepted_commitment_mw === 0 ? "No positive commitment was accepted. Review the calibration evidence and explanation."
        : "Simulation executed. Results below are model outputs; any reliability statistics describe calibration evidence.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `Simulation error: ${error.message}`
          : "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  const chartData =
    simulation?.telemetry.event_time_series.map((point) => ({
      minute: point.end_minute,
      baseline: point.baseline_grid_import_mw,
      gridImport: point.grid_import_mw,
      batterySoC: point.battery_soc_end * 100,
      backlog: point.workload_backlog_mwh,
    })) ?? [];

  return (
    <div className="planner-page">
      <p className="eyebrow">GRID FLEXIBILITY</p>
      <h1>Flexibility Commitment Planner</h1>
      <p className="subtitle">
        Configure FP-001 and select nominal execution or an existing Member 1 controller.
      </p>

      <section className="panel planner-panel">
        <div className="panel-header">
          <div>
            <h2>Event Configuration</h2>
            <p>Enter the scenario parameters below.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="planner-form">
          <label>Controller<select aria-label="Controller" value={controller} onChange={(e) => setController(e.target.value)}>
            <option value="nominal">Nominal illustration</option><option value="rafc_v">RAFC-V</option><option value="risk_aware_mpc">Risk-aware MPC</option><option value="deterministic_mpc">Deterministic MPC</option><option value="rule_based">Rule based</option>
          </select></label>
          <label>
            Requested reduction (MW)
            <input
              type="number"
              min="0.1"
              max="20"
              step="0.1"
              value={requestedMW}
              onChange={(e) => setRequestedMW(Number(e.target.value))}
              required
            />
          </label>

          <label>
            Event duration
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            >
              <option value={15}>15 minutes</option>
              <option value={30}>30 minutes</option>
              <option value={60}>60 minutes</option>
            </select>
          </label>

          <label>
            Reliability target
            <select
              value={reliability}
              onChange={(e) => setReliability(Number(e.target.value))}
            >
              <option value={90}>90%</option>
              <option value={95}>95%</option>
              <option value={99}>99%</option>
            </select>
          </label>

          <label>
            Battery initial SoC (%)
            <input
              type="number"
              min="20"
              max="100"
              step="1"
              value={batterySoC}
              onChange={(e) => setBatterySoC(Number(e.target.value))}
              required
            />
          </label>

          <button
            type="submit"
            className="primary-button"
            disabled={loading}
          >
            {loading ? "Running Simulation..." : "Run Simulation"}
          </button>
          <label>Random seed<input type="number" min="0" step="1" value={seed} onChange={(e) => setSeed(Number(e.target.value))} required /></label>
          <label>Calibration scenarios<input type="number" min="100" max="5000" step="100" value={calibrationScenarios} onChange={(e) => setCalibrationScenarios(Number(e.target.value))} required /></label>
          <label>Recovery grid ceiling (MW)<input type="number" min="17" max="30" step="1" value={recoveryCeiling} onChange={(e) => setRecoveryCeiling(Number(e.target.value))} required /></label>
          <button type="button" className="primary-button" disabled={loading} onClick={() => void handleAssessment()}>Assess Commitment</button>
        </form>

        {loading && <p role="status">Running the simulation engine…</p>}

        {message && (
          <div className="notice" role="status">
            {message}
          </div>
        )}
      </section>

      {assessment && <section className="panel planner-results"><h2>Recovery-aware commitment assessment</h2>
        <p>Requested {formatNumber(assessment.requested_reduction_mw)} MW · Recommended {formatNumber(assessment.recommended_commitment_mw)} MW · Target {(assessment.reliability_target * 100).toFixed(1)}%</p>
        <p>Status: <strong>{assessment.feasibility_status}</strong> · {assessment.controller_version}</p><p>{assessment.explanation}</p>
        <p>Calibration estimate: {formatNumber(assessment.calibration.estimate == null ? null : assessment.calibration.estimate * 100)}% · Simultaneous lower bound: {formatNumber(assessment.calibration.simultaneous_lower_bound == null ? null : assessment.calibration.simultaneous_lower_bound * 100)}% · {assessment.calibration.sample_count} samples.</p>
        <p>Held-out validation: {assessment.held_out_validation.status}. {assessment.held_out_validation.reason}</p>
      </section>}

      {simulation && (
        <section className="panel planner-results">
          <div className="panel-header">
            <div>
              <p className="eyebrow">FP-001 RESULTS</p>
              <h2>{simulation.controller === "nominal_illustration" ? "Nominal Simulation Results" : "Simulation Results"}</h2>
              <p>{simulation.controller} · {simulation.controller_version}</p>
              <p>Run ID: {simulation.run_id}</p>
            </div>
          </div>

          <div className="simulation-metrics">
            <div className="simulation-metric">
              <span>Accepted Commitment</span>
              <strong>
                {formatNumber(simulation.accepted_commitment_mw)} MW
              </strong>
            </div>

            <div className="simulation-metric">
              <span>Execution Status</span>
              <strong>{simulation.execution_status}</strong>
            </div>

            <div className="simulation-metric">
              <span>Complete Event Success</span>
              <strong>
                {simulation.complete_event_success == null ? "Not evaluated" : simulation.complete_event_success ? "Yes" : "No"}
              </strong>
            </div>

            <div className="simulation-metric">
              <span>Final Battery SoC</span>
              <strong>
                {formatNumber(
                  (simulation.telemetry.final_battery_soc ?? NaN) * 100
                )}
                %
              </strong>
            </div>

            <div className="simulation-metric">
              <span>Final Workload Backlog</span>
              <strong>
                {formatNumber(
                  simulation.telemetry.final_workload_backlog_mwh
                )}{" "}
                MWh
              </strong>
            </div>

            <div className="simulation-metric">
              <span>Constraint Violations</span>
              <strong>{simulation.violations?.length ?? 0}</strong>
            </div>
          </div>

          {simulation.infeasibility_reason && <div className="notice" role="alert">{simulation.infeasibility_reason}</div>}

          <p className="simulation-disclaimer">
            Reliability evaluation: {simulation.reliability?.status ?? "Unavailable"}.
            {simulation.reliability?.evidence_split === "calibration" ? ` Estimate ${formatNumber((simulation.reliability.estimate ?? NaN) * 100)}%; lower confidence bound ${formatNumber((simulation.reliability.confidence_lower_bound ?? NaN) * 100)}%; ${simulation.reliability.sample_count} calibration scenarios. Held-out validation is unavailable for this run.` : " This deterministic execution does not evaluate the reliability target."}
          </p>

          {chartData.length > 0 && (
            <>
              <div className="simulation-chart">
                <h3>Grid Import During Event (MW)</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="minute"
                      label={{
                        value: "Time (minutes)",
                        position: "insideBottom",
                        offset: -5,
                      }}
                    />
                    <YAxis />
                    <Tooltip />
                    <Line
                      isAnimationActive={false}
                      type="monotone"
                      dataKey="baseline"
                      name="Baseline Grid Import"
                      stroke="#6b7280"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      isAnimationActive={false}
                      type="monotone"
                      dataKey="gridImport"
                      name="Actual Grid Import"
                      stroke="#d5a728"
                      strokeWidth={3}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="simulation-chart">
                <h3>Battery State of Charge (%)</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="minute" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Line
                      isAnimationActive={false}
                      type="monotone"
                      dataKey="batterySoC"
                      name="Battery SoC (%)"
                      stroke="#2563eb"
                      strokeWidth={3}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="simulation-chart">
                <h3>Remaining Workload Backlog (MWh)</h3>
                <p>{simulation.controller === "nominal_illustration" ? "The nominal model releases the event workload cohort at minute zero; remaining work at event end is deferred to recovery." : "Backlog follows the selected controller's returned workload telemetry."}</p>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="minute" />
                    <YAxis />
                    <Tooltip />
                    <Line
                      isAnimationActive={false}
                      type="monotone"
                      dataKey="backlog"
                      name="Workload Backlog"
                      stroke="#0f766e"
                      strokeWidth={3}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}

          <div className="simulation-disclaimer">
            This result is a simulated execution. Calibration evidence, event delivery, recovery feasibility and operational verification are separate checks; none is utility certification.
          </div>
        </section>
      )}
    </div>
  );
}
