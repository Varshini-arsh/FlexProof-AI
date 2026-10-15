import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RecordedRun } from "./CommitmentPlanner";

const number = (value: number | null | undefined, digits = 3) => value == null || !Number.isFinite(value) ? "Unavailable" : value.toFixed(digits);

export default function GridEventMonitor({ run, onPlan }: { run: RecordedRun | null; onPlan: () => void }) {
  if (!run) return <section className="panel"><h1>Grid Event Monitor</h1><p>No simulation evidence is selected. Run a scenario to monitor its returned intervals.</p><button type="button" className="primary-button" onClick={onPlan}>Open Commitment Planner</button></section>;
  const { result, request } = run;
  const rows = result.telemetry.event_time_series;
  const data = rows.map((row) => ({ ...row, minute: row.end_minute,
    delivered: row.baseline_grid_import_mw - row.grid_import_mw,
    requested: request.requested_reduction_mw, commitment: result.accepted_commitment_mw,
  }));
  return <div className="planner-page">
    <p className="eyebrow">RECORDED SIMULATION EVIDENCE</p><h1>Grid Event Monitor</h1>
    <p className="subtitle">{result.scenario_id} · {result.run_id} · {result.execution_status}</p>
    <div className="notice">Delivered reduction is recomputed as baseline minus grid import. All measurements here come from the selected simulation run.</div>
    <section className="panel planner-results">
      <div className="simulation-metrics">
        <div className="simulation-metric"><span>Requested reduction</span><strong>{number(request.requested_reduction_mw)} MW</strong></div>
        <div className="simulation-metric"><span>Accepted commitment</span><strong>{number(result.accepted_commitment_mw)} MW</strong></div>
        <div className="simulation-metric"><span>Recorded intervals</span><strong>{rows.length} / {request.duration_minutes / 5}</strong></div>
      </div>
      <div className="simulation-chart"><h2>Requested, committed and delivered reduction (MW)</h2>
        <ResponsiveContainer width="100%" height={300}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis /><Tooltip /><Legend />
          <Line isAnimationActive={false} dataKey="requested" name="Requested" stroke="#b45309" strokeDasharray="5 5" dot={false} />
          <Line isAnimationActive={false} dataKey="commitment" name="Accepted" stroke="#2563eb" dot={false} />
          <Line isAnimationActive={false} dataKey="delivered" name="Delivered" stroke="#0f766e" dot={false} />
        </LineChart></ResponsiveContainer>
      </div>
      <div className="simulation-chart"><h2>Baseline and actual import (MW)</h2>
        <ResponsiveContainer width="100%" height={280}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" /><YAxis /><Tooltip /><Legend />
          <Line isAnimationActive={false} dataKey="baseline_grid_import_mw" name="Baseline" stroke="#64748b" dot={false} />
          <Line isAnimationActive={false} dataKey="grid_import_mw" name="Actual import" stroke="#d5a728" dot={false} />
        </LineChart></ResponsiveContainer>
      </div>
      <h2>Interval evidence</h2>
      <div className="telemetry-table"><table><thead><tr><th>Minutes</th><th>Baseline MW</th><th>Import MW</th><th>Delivered MW</th><th>Battery discharge MW</th><th>SoC %</th><th>Flexible compute MW</th><th>Backlog MWh</th><th>Commitment check</th><th>Reported violations</th></tr></thead>
        <tbody>{data.map((row) => {
          const violations = result.violations.filter((item) => item.minute != null && item.minute >= row.start_minute && item.minute < row.end_minute);
          const met = result.accepted_commitment_mw == null ? null : row.delivered + 1e-7 >= result.accepted_commitment_mw;
          return <tr key={row.step} data-testid="event-interval-row"><td>{row.start_minute}–{row.end_minute}</td><td>{number(row.baseline_grid_import_mw)}</td><td>{number(row.grid_import_mw)}</td><td>{number(row.delivered)}</td><td>{number(row.battery_discharge_mw)}</td><td>{number(row.battery_soc_end * 100)}</td><td>{number(row.flexible_compute_mw)}</td><td>{number(row.workload_backlog_mwh)}</td><td>{met == null ? "Not evaluated" : met ? "Met" : "Shortfall"}</td><td>{violations.length ? violations.map((item) => item.reason ?? item.type ?? "Constraint violation").join("; ") : "None reported"}</td></tr>;
        })}</tbody></table></div>
      {rows.length === 0 && <p>No event interval evidence was returned.</p>}
      {result.violations.length > 0 && <div role="alert"><h3>Recorded constraint violations</h3><pre>{JSON.stringify(result.violations, null, 2)}</pre></div>}
      <p className="simulation-disclaimer">This monitor displays a recorded simulation, rather than a live datacentre feed. Missing values are shown as unavailable. Independent operational verification is a subsequent check.</p>
    </section>
  </div>;
}
