
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

type TelemetryPoint = {
  step: number;
  start_minute: number;
  end_minute: number;
  baseline_grid_import_mw: number;
  grid_import_mw: number;
  battery_soc_end: number;
  workload_backlog_mwh: number;
  battery_discharge_mw: number;
};

type SimulationResult = {
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
  };
  telemetry: {
    event_time_series: TelemetryPoint[];
    final_battery_soc: number;
    final_workload_backlog_mwh: number;
  };
  violations: unknown[];
};

type SimulationResponse = {
  status: string;
  simulation_type: string;
  reliability_certified: boolean;
  result: SimulationResult;
};

const formatNumber = (value: number | null | undefined, digits = 2) =>
  value != null && Number.isFinite(value) ? value.toFixed(digits) : "N/A";

export default function CommitmentPlanner() {
  const [requestedMW, setRequestedMW] = useState(5);
  const [duration, setDuration] = useState(60);
  const [reliability, setReliability] = useState(95);
  const [batterySoC, setBatterySoC] = useState(35);

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setMessage("");
    setSimulation(null);

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

    const scenario = {
      scenario_id: "FP-001",
      requested_reduction_mw: requestedMW,
      duration_minutes: duration,
      reliability_target: reliability / 100,
      battery_soc_percent: batterySoC,
    };

    setLoading(true);

    try {
      const data = await apiRequest<SimulationResponse>("/scenarios/run", {
        method: "POST", body: JSON.stringify(scenario),
      });

      if (!data.result || !data.result.telemetry) {
        throw new Error("The backend returned an incomplete simulation result.");
      }

      setSimulation(data.result);
      setMessage(data.result.status === "infeasible"
        ? "The nominal dispatch is infeasible. Inspect the returned constraints and partial evidence below."
        : "Nominal simulation executed. Results below are model outputs, not reliability-certified commitments.");
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
        Configure and execute the nominal FP-001 datacentre simulation.
      </p>

      <section className="panel planner-panel">
        <div className="panel-header">
          <div>
            <h2>Event Configuration</h2>
            <p>Enter the scenario parameters below.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="planner-form">
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
        </form>

        {loading && <p role="status">Running the simulation engine…</p>}

        {message && (
          <div className="notice" role="status">
            {message}
          </div>
        )}
      </section>

      {simulation && (
        <section className="panel planner-results">
          <div className="panel-header">
            <div>
              <p className="eyebrow">FP-001 RESULTS</p>
              <h2>Nominal Simulation Results</h2>
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
                  simulation.telemetry.final_battery_soc * 100
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
            Reliability evaluation: {simulation.reliability.status}.
            The selected reliability target is not certified by this
            nominal simulation. Recovery is not evaluated here.
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
                <p>The nominal model releases the event workload cohort at minute zero; remaining work at event end is deferred to recovery.</p>
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
            This result represents one deterministic nominal dispatch.
            It does not demonstrate a 95% event-success probability,
            RAFC-V optimization performance, or successful recovery.
          </div>
        </section>
      )}
    </div>
  );
}
