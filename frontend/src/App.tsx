
import { useEffect, useState, type ReactNode } from "react";
import {
  BatteryCharging,
  CircleCheck,
  LayoutDashboard,
  Menu,
  Play,
  Server,
  Settings2,
  ShieldCheck,
  X,
  Zap,
} from "lucide-react";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import CommitmentPlanner from "./pages/CommitmentPlanner";
import RunsPage from "./pages/RunsPage";
import { API_BASE } from "./api";
import "./App.css";

// Illustrative FP-001 data, not actual simulation results.
const powerData = [
  { time: "0", baseline: 20, grid: 20 },
  { time: "10", baseline: 20, grid: 17 },
  { time: "20", baseline: 20, grid: 15.4 },
  { time: "30", baseline: 20, grid: 15.1 },
  { time: "40", baseline: 20, grid: 15.3 },
  { time: "50", baseline: 20, grid: 15.5 },
  { time: "60", baseline: 20, grid: 15.2 },
];

const navigation = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Commitment Planner", icon: Settings2 },
  { name: "Run History", icon: BatteryCharging },
];

function App() {
  const [activePage, setActivePage] = useState("Overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState("Checking API");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/health`).then((response) => {
      if (!response.ok) throw new Error("API unavailable");
      return response.json() as Promise<{ simulation_connected?: boolean }>;
    }).then((health) => {
      if (active) setApiStatus(health.simulation_connected ? "Engine connected" : "API available");
    }).catch(() => { if (active) setApiStatus("API offline"); });
    return () => { active = false; };
  }, []);

  return (
    <div className="app">
      {/* Sidebar */}
      <aside
        className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}
      >
        <div className="brand">
          <div className="brand-mark">
            <Zap size={22} />
          </div>

          <div>
            <strong>FlexProof AI</strong>
            <span>YellowSense Technologies</span>
          </div>

          <button
            type="button"
            className="mobile-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav>
          {navigation.map(({ name, icon: Icon }) => (
            <button
              key={name}
              type="button"
              className={`nav-item ${
                activePage === name ? "active" : ""
              }`}
              onClick={() => {
                setActivePage(name);
                setSidebarOpen(false);
              }}
            >
              <Icon size={19} />
              <span>{name}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <ShieldCheck size={17} />
          <span>Research Prototype</span>
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
        />
      )}

      {/* Main application */}
      <main className="main">
        <header className="topbar">
          <button
            type="button"
            className="menu-button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={22} />
          </button>

          <div className="breadcrumb">
            Workspace / {activePage}
          </div>

          <div className="topbar-right">
            <span className="demo-badge">
              {apiStatus.toUpperCase()}
            </span>

            <span className="avatar">YS</span>
          </div>
        </header>

        <div className="content">
          {/* Overview */}
          {activePage === "Overview" ? (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">
                    FACILITY MONITORING
                  </p>

                  <h1>Datacentre Overview</h1>

                  <p className="subtitle">
                    Explore facility demand, energy
                    resources and grid flexibility
                    using illustrative FP-001 data.
                  </p>
                </div>

                <button
                  type="button"
                  className="primary-button"
                  onClick={() =>
                    setActivePage("Commitment Planner")
                  }
                >
                  <Play size={16} />
                  Plan Flexibility
                </button>
              </div>

              <div className="notice">
                <ShieldCheck size={18} />

                <span>
                  Interface preview — values below
                  are illustrative. No live datacentre
                  or simulation API connection is active.
                </span>
              </div>

              {/* Statistics */}
              <div className="stat-grid">
                <StatCard
                  label="Reference Facility Demand"
                  value="20.0"
                  unit="MW"
                  icon={<Server size={21} />}
                  description="FP-001 assumed baseline"
                />

                <StatCard
                  label="Battery State of Charge"
                  value="35"
                  unit="%"
                  icon={<BatteryCharging size={21} />}
                  description="20% protected minimum"
                />

                <StatCard
                  label="Requested Reduction"
                  value="5.0"
                  unit="MW"
                  icon={<Zap size={21} />}
                  description="60-minute scenario request"
                />

                <StatCard
                  label="Scenario Status"
                  value="Preview"
                  unit=""
                  icon={<CircleCheck size={21} />}
                  description="No simulation currently running"
                />
              </div>

              {/* Dashboard panels */}
              <div className="dashboard-grid">
                <section className="panel chart-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Grid Import Profile</h2>
                      <p>
                        Illustrative 60-minute
                        curtailment event
                      </p>
                    </div>

                    <span className="panel-tag">
                      FP-001 • Example
                    </span>
                  </div>

                  <div className="chart-container">
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >
                      <LineChart
                        data={powerData}
                        margin={{
                          top: 8,
                          right: 10,
                          left: -15,
                          bottom: 8,
                        }}
                      >
                        <CartesianGrid
                          stroke="#e9edf2"
                          strokeDasharray="4 4"
                        />

                        <XAxis
                          dataKey="time"
                          tickLine={false}
                          axisLine={false}
                          tick={{
                            fill: "#84909f",
                            fontSize: 12,
                          }}
                        />

                        <YAxis
                          domain={[10, 22]}
                          tickLine={false}
                          axisLine={false}
                          tick={{
                            fill: "#84909f",
                            fontSize: 12,
                          }}
                        />

                        <Tooltip
                          formatter={(value) => [
                            `${value} MW`,
                          ]}
                        />

                        <Legend />

                        <Line
                          type="monotone"
                          dataKey="baseline"
                          name="Baseline (MW)"
                          stroke="#94a3b8"
                          strokeWidth={2.5}
                          dot={false}
                        />

                        <Line
                          type="monotone"
                          dataKey="grid"
                          name="Example Import (MW)"
                          stroke="#e5ad15"
                          strokeWidth={3}
                          dot={{ r: 3 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  <p className="chart-caption">
                    Time (minutes) · Mock values,
                    not experiment results
                  </p>
                </section>

                {/* Resource panel */}
                <section className="panel resources-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Facility Resources</h2>

                      <p>
                        Initial FP-001 assumptions
                      </p>
                    </div>
                  </div>

                  <ResourceBar
                    name="Critical AI Load"
                    value={12}
                    total={20}
                  />

                  <ResourceBar
                    name="Fixed Facility Load"
                    value={4}
                    total={20}
                  />

                  <ResourceBar
                    name="Flexible Compute"
                    value={4}
                    total={20}
                  />

                  <div className="battery-block">
                    <div className="battery-heading">
                      <span>Battery Energy</span>
                      <strong>35% SoC</strong>
                    </div>

                    <div className="battery-track">
                      <div className="battery-progress" />
                    </div>

                    <p>
                      10 MWh capacity · 20%
                      protected reserve
                    </p>
                  </div>
                </section>
              </div>
            </>
          ) : activePage === "Commitment Planner" ? (
            /* Commitment Planner page */
            <CommitmentPlanner />
          ) : activePage === "Run History" ? (
            <RunsPage />
          ) : (
            /* Future pages */
            <div className="placeholder-page">
              <div className="placeholder-icon">
                <Settings2 size={30} />
              </div>

              <p className="eyebrow">
                COMING NEXT
              </p>

              <h1>{activePage}</h1>

              <p>
                This module will be developed in
                the next Member 2 milestones.
                It will use real outputs from the
                shared FlexProof AI engine.
              </p>

              <button
                type="button"
                className="primary-button"
                onClick={() => setActivePage("Overview")}
              >
                Back to Overview
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// Reusable statistics card
function StatCard({
  label,
  value,
  unit,
  icon,
  description,
}: {
  label: string;
  value: string;
  unit: string;
  icon: ReactNode;
  description: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{label}</span>

        <div className="stat-icon">
          {icon}
        </div>
      </div>

      <div className="stat-value">
        {value} <small>{unit}</small>
      </div>

      <p>{description}</p>
    </div>
  );
}

// Reusable facility resource progress bar
function ResourceBar({
  name,
  value,
  total,
}: {
  name: string;
  value: number;
  total: number;
}) {
  return (
    <div className="resource">
      <div className="resource-heading">
        <span>{name}</span>
        <strong>{value} MW</strong>
      </div>

      <div className="resource-track">
        <div
          className="resource-progress"
          style={{
            width: `${(value / total) * 100}%`,
          }}
        />
      </div>
    </div>
  );
}

export default App;
