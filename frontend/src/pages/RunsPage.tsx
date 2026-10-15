import { useCallback, useEffect, useState } from "react";
import { API_BASE, apiRequest } from "../api";

type RunSummary = {
  run_id: string;
  scenario_id: string;
  controller: string;
  status: string;
  created_at: string;
  accepted_commitment_mw: number | null;
  verification_status: string;
};

type RunRecord = {
  result: {
    run_id: string;
    scenario_id: string;
    controller: string;
    accepted_commitment_mw: number | null;
    reliability: { status?: string; estimate?: number | null; confidence_lower_bound?: number | null } | null;
    telemetry: { event_time_series: Array<{ end_minute: number; grid_import_mw: number; delivered_reduction_mw?: number }> };
  };
  verification: { status: string; check_count: number; failed_check_count: number; certification: boolean };
};

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<RunRecord | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setError("");
      const value = await apiRequest<{ runs: RunSummary[] }>("/runs?limit=50");
      setRuns(value.runs);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load run history.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function openRun(runId: string) {
    try {
      setError("");
      setSelected(await apiRequest<RunRecord>(`/runs/${encodeURIComponent(runId)}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load run details.");
    }
  }

  return <div className="planner-page">
    <p className="eyebrow">PERSISTED RUNS</p>
    <h1>Simulation Run History</h1>
    <p className="subtitle">Results are stored locally in the prototype SQLite database.</p>
    <section className="panel planner-panel">
      <div className="panel-header"><div><h2>Recent runs</h2><p>{runs.length} runs</p></div>
        <button className="primary-button" type="button" onClick={() => void refresh()}>Refresh</button></div>
      {loading && <p role="status">Loading run history…</p>}
      {error && <div className="notice" role="alert">{error}</div>}
      {!loading && runs.length === 0 && <p>No saved runs yet. Use Commitment Planner to run a scenario.</p>}
      {runs.length > 0 && <div className="run-list">
        {runs.map((run) => <button className="run-row" type="button" key={run.run_id} onClick={() => void openRun(run.run_id)}>
          <span><strong>{run.scenario_id}</strong><small>{run.controller} · {new Date(run.created_at).toLocaleString()}</small></span>
          <span>{run.accepted_commitment_mw == null ? "No commitment" : `${run.accepted_commitment_mw.toFixed(2)} MW`}</span>
          <span>{run.status} · check {run.verification_status}</span>
        </button>)}
      </div>}
    </section>
    {selected && <section className="panel planner-results">
      <div className="panel-header"><div><p className="eyebrow">RUN DETAIL</p><h2>{selected.result.scenario_id}</h2><p>{selected.result.run_id}</p></div>
        <a className="primary-button" href={`${API_BASE}/runs/${encodeURIComponent(selected.result.run_id)}/report.pdf`}>Download PDF report</a></div>
      <p>Controller: <strong>{selected.result.controller}</strong> · Commitment: <strong>{selected.result.accepted_commitment_mw == null ? "none" : `${selected.result.accepted_commitment_mw.toFixed(2)} MW`}</strong></p>
      <p>Reliability evidence: {selected.result.reliability?.status ?? "not evaluated"}; estimate {selected.result.reliability?.estimate == null ? "not available" : `${(selected.result.reliability.estimate * 100).toFixed(2)}%`}. This is calibration evidence, not held-out validation.</p>
      <p>Independent arithmetic checks: <strong>{selected.verification.status}</strong> ({selected.verification.check_count} checks, {selected.verification.failed_check_count} failed). This is not certification.</p>
      <p>Event telemetry points: {selected.result.telemetry.event_time_series.length}</p>
    </section>}
  </div>;
}
