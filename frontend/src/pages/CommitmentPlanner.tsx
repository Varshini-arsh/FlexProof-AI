
import { useState, type FormEvent } from "react";

type ValidationResponse = {
  status: string;
  message: string;
  simulation_connected: boolean;
};

export default function CommitmentPlanner() {
  const [requestedMW, setRequestedMW] = useState(5);
  const [duration, setDuration] = useState(60);
  const [reliability, setReliability] = useState(95);
  const [batterySoC, setBatterySoC] = useState(35);

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");

    if (requestedMW <= 0 || requestedMW > 20) {
      setMessage("Requested reduction must be greater than 0 and at most 20 MW.");
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
      const response = await fetch(
        "http://127.0.0.1:8000/api/scenarios/validate",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(scenario),
        }
      );

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const data: ValidationResponse = await response.json();
      setMessage(data.message);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? `Connection error: ${error.message}`
          : "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="planner-page">
      <p className="eyebrow">GRID FLEXIBILITY</p>
      <h1>Flexibility Commitment Planner</h1>
      <p className="subtitle">
        Configure a grid curtailment request for FP-001.
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
            {loading ? "Validating..." : "Validate Scenario"}
          </button>
        </form>

        {message && (
          <div className="notice" role="status">
            {message}
          </div>
        )}
      </section>
    </div>
  );
}
