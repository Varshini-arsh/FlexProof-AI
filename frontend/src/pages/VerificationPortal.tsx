import { useState } from "react";
import { API_BASE, apiRequest } from "../api";
import type { RecordedRun, VerificationResult } from "./CommitmentPlanner";

export default function VerificationPortal({run, onPlan, onVerified}: {
  run: RecordedRun | null; onPlan: () => void; onVerified: (value: VerificationResult) => void;
}) {
  const [verification, setVerification] = useState<VerificationResult | null>(run?.verification ?? null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState("");
  const [error, setError] = useState("");
  if (!run) return <section className="panel"><h1>Verification Portal</h1><p>No recorded simulation is selected. Run a scenario to create evidence.</p><button className="primary-button" type="button" onClick={onPlan}>Open Commitment Planner</button></section>;
  const selectedRun = run;
  async function verifyAgain() {
    setLoading(true); setError("");
    try {
      const result = await apiRequest<VerificationResult>("/evidence/verify", {method: "POST", body: JSON.stringify({
        scenario: selectedRun.config, result: selectedRun.result,
        expected_input_hash: verification?.metrics.input_hash,
        expected_evidence_hash: verification?.metrics.evidence_hash,
      })});
      setVerification(result); onVerified(result);
    } catch (err) { setError(err instanceof Error ? err.message : "Verification API unavailable"); }
    finally { setLoading(false); }
  }
  async function downloadEvidence(format: "json" | "csv" | "pdf") {
    setExporting(format); setError("");
    const route = format === "json" ? "/evidence/export" : format === "csv" ? "/evidence/telemetry.csv" : "/evidence/report.pdf";
    try {
      const response = await fetch(`${API_BASE}${route}`, {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({scenario: selectedRun.config, result: selectedRun.result})});
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `${selectedRun.result.run_id}-evidence.${format}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err instanceof Error ? err.message : "Evidence export failed"); }
    finally { setExporting(""); }
  }
  const current = verification ?? run.verification ?? null;
  return <div className="planner-page"><p className="eyebrow">INDEPENDENT EVIDENCE REVIEW</p><h1>Verification Portal</h1>
    <p className="subtitle">Scenario {run.result.scenario_id} · Run {run.result.run_id}</p>
    <section className="panel planner-results">
      <div className="simulation-metrics">
        <Metric label="Verification status" value={current?.status ?? "Not available"} testId="verification-overall" />
        <Metric label="Checks passed" value={current ? String(current.check_count - current.failed_check_count - current.insufficient_check_count) : "N/A"} />
        <Metric label="Checks failed" value={current ? String(current.failed_check_count) : "N/A"} />
        <Metric label="Evidence incomplete" value={current ? String(current.insufficient_check_count) : "N/A"} />
        <Metric label="Verifier version" value={current?.verifier_version ?? "N/A"} />
      </div>
      <p>{current?.scope ?? "The API will independently recompute the recorded electrical and aggregate workload evidence."}</p>
      <button className="primary-button" type="button" onClick={verifyAgain} disabled={loading}>{loading ? "Verifying…" : "Re-verify recorded evidence"}</button>
      <div className="evidence-export-actions" aria-label="Download evidence">
        <button type="button" onClick={() => downloadEvidence("json")} disabled={Boolean(exporting)}>{exporting === "json" ? "Preparing JSON…" : "Download JSON evidence"}</button>
        <button type="button" onClick={() => downloadEvidence("csv")} disabled={Boolean(exporting)}>{exporting === "csv" ? "Preparing CSV…" : "Download telemetry CSV"}</button>
        <button type="button" onClick={() => downloadEvidence("pdf")} disabled={Boolean(exporting)}>{exporting === "pdf" ? "Preparing PDF…" : "Download verification PDF"}</button>
      </div>
      {error && <p role="alert">Verification error: {error}</p>}
      {current && <>
        <h2>Verification checks</h2>
        <div className="telemetry-table"><table><thead><tr><th>Check</th><th>Status</th><th>Finding</th></tr></thead><tbody>
          {current.checks.map((check) => <tr key={check.name}><td>{check.name}</td><td>{check.status}</td><td>{check.detail}</td></tr>)}
        </tbody></table></div>
        <h2>Evidence hashes</h2><dl className="evidence-hashes"><dt>Input SHA-256</dt><dd>{String(current.metrics.input_hash ?? "Unavailable")}</dd><dt>Evidence SHA-256</dt><dd>{String(current.metrics.evidence_hash ?? "Unavailable")}</dd></dl>
        <p className="simulation-disclaimer">A passing result checks supplied simulation telemetry against the documented model. It is not field validation, a digital signature, or utility certification.</p>
        <h2>Scope limitations</h2><ul>{current.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </>}
    </section></div>;
}

function Metric({label, value, testId}: {label: string; value: string; testId?: string}) {
  return <div className="simulation-metric" data-testid={testId}><span>{label}</span><strong>{value}</strong></div>;
}
