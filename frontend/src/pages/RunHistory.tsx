import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { RecordedRun } from "./CommitmentPlanner";

type RunRow = {run_id: string; scenario_id: string; controller: string; controller_version: string;
  status: string; execution_status: string; created_at: string | null};
type RunList = {runs: RunRow[]};
type StoredRun = {request: RecordedRun["request"]; scenario: RecordedRun["config"];
  result: RecordedRun["result"]; independent_verification?: RecordedRun["verification"]};

export default function RunHistory({onSelect}: {onSelect: (run: RecordedRun) => void}) {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState("");
  useEffect(() => { apiRequest<RunList>("/runs").then((data) => setRuns(data.runs))
    .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Run history unavailable")); }, []);
  async function open(runId: string) {
    setLoading(runId); setError("");
    try {
      const stored = await apiRequest<StoredRun>(`/runs/${encodeURIComponent(runId)}`);
      onSelect({request: stored.request, config: stored.scenario, result: stored.result, verification: stored.independent_verification});
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load the saved run"); }
    finally { setLoading(""); }
  }
  return <div className="planner-page"><p className="eyebrow">PERSISTED SIMULATION RECORDS</p><h1>Run History</h1>
    <p className="subtitle">Saved scenarios, event/recovery telemetry, and independent verification from the configured database.</p>
    {error && <p role="alert">Run history error: {error}</p>}
    {runs.length === 0 ? <section className="panel">No saved runs are available. Execute a scenario after applying the database migrations.</section> :
      <section className="panel"><div className="telemetry-table"><table><thead><tr><th>Run ID</th><th>Scenario</th><th>Controller</th><th>Run status</th><th>Execution</th><th>Recorded</th><th>Action</th></tr></thead>
        <tbody>{runs.map((run) => <tr key={run.run_id}><td>{run.run_id}</td><td>{run.scenario_id}</td><td>{run.controller}</td><td>{run.status}</td><td>{run.execution_status}</td><td>{run.created_at ?? "Unavailable"}</td>
          <td><button type="button" onClick={() => open(run.run_id)} disabled={Boolean(loading)}>{loading === run.run_id ? "Loading…" : "Open run"}</button></td></tr>)}</tbody></table></div></section>}
  </div>;
}
