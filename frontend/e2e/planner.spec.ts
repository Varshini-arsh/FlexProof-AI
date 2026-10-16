import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Commitment Planner", exact: true }).click();
});

test("React runs FP-001 and renders actual API telemetry", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/scenarios/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run Simulation", exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const runBody = await response.json();
  const { result, reliability_certified } = runBody;
  expect(reliability_certified).toBe(false);
  expect(runBody.independent_verification.status).toBe("pass");
  expect(result.telemetry.event_time_series).toHaveLength(12);
  await expect(page.getByRole("heading", { name: "Nominal Simulation Results" })).toBeVisible();
  const card = (name: string) => page.locator(".simulation-metric").filter({ hasText: name }).locator("strong");
  await expect(card("Accepted Commitment")).toHaveText(`${result.accepted_commitment_mw.toFixed(2)} MW`);
  await expect(card("Final Battery SoC")).toHaveText(`${(result.telemetry.final_battery_soc * 100).toFixed(2)}%`);
  await expect(card("Final Workload Backlog")).toHaveText(`${result.telemetry.final_workload_backlog_mwh.toFixed(2)} MWh`);
  await expect(page.locator(".simulation-metric")).toHaveCount(6);
  await expect(page.locator(".simulation-chart svg.recharts-surface")).toHaveCount(3);
  expect(errors).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("fp001-nominal.png"), fullPage: true });
  await page.getByRole("button", { name: "Grid Event Monitor", exact: true }).click();
  await expect(page.getByTestId("event-interval-row")).toHaveCount(12);
  const first = page.getByTestId("event-interval-row").first().locator("td");
  await expect(first.nth(2)).toHaveText(result.telemetry.event_time_series[0].grid_import_mw.toFixed(3));
  await expect(first.nth(3)).toHaveText((result.telemetry.event_time_series[0].baseline_grid_import_mw - result.telemetry.event_time_series[0].grid_import_mw).toFixed(3));
  await page.screenshot({ path: test.info().outputPath("fp001-monitor.png"), fullPage: true });
  await page.getByRole("button", { name: "Commitment Planner", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Nominal Simulation Results" })).toBeVisible();
  await page.getByRole("button", { name: "Verification Portal", exact: true }).click();
  await expect(page.getByTestId("verification-overall").locator("strong")).toHaveText("pass");
  const verifyResponse = page.waitForResponse((response) => response.url().endsWith("/api/evidence/verify"));
  await page.getByRole("button", { name: "Re-verify recorded evidence" }).click();
  const verificationBody = await (await verifyResponse).json();
  expect(verificationBody.status).toBe("pass");
  await expect(page.getByTestId("verification-overall").locator("strong")).toHaveText("pass");
  const jsonDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", {name: "Download JSON evidence"}).click();
  expect((await jsonDownloadPromise).suggestedFilename()).toMatch(/-evidence\.json$/);
  const csvDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", {name: "Download telemetry CSV"}).click();
  expect((await csvDownloadPromise).suggestedFilename()).toMatch(/-evidence\.csv$/);
  const pdfDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", {name: "Download verification PDF"}).click();
  expect((await pdfDownloadPromise).suggestedFilename()).toMatch(/-evidence\.pdf$/);
});

test("infeasible request explains the API rejection", async ({ page }) => {
  await page.getByLabel("Requested reduction (MW)").fill("20");
  await page.getByRole("button", { name: "Run Simulation", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Simulation error:");
  await expect(page.getByRole("status")).toContainText("capability");
  await expect(page.locator(".planner-results")).toHaveCount(0);
});

test("protected reserve produces an infeasible result", async ({ page }) => {
  await page.getByLabel("Battery initial SoC (%)").fill("20");
  await page.getByRole("button", { name: "Run Simulation", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("infeasible");
  await expect(page.getByRole("alert")).toContainText("constraints failed");
  await expect(page.locator(".simulation-metric").filter({ hasText: "Complete Event Success" })).toContainText("No");
});

test("API connection failure is visible and run control is re-enabled", async ({ page }) => {
  await page.route("**/api/scenarios/run", (route) => route.abort("failed"));
  await page.getByRole("button", { name: "Run Simulation", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Simulation error:");
  await expect(page.getByRole("button", { name: "Run Simulation", exact: true })).toBeEnabled();
});

test("RAFC-V execution shows calibration evidence and actual monitored intervals", async ({ page }) => {
  await page.getByLabel("Controller", { exact: true }).selectOption("rafc_v");
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/scenarios/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run Simulation", exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const { result } = await response.json();
  expect(result.controller).toBe("rafc_v");
  expect(result.reliability.evidence_split).toBe("calibration");
  await expect(page.getByRole("heading", { name: "Simulation Results", exact: true })).toBeVisible();
  await expect(page.getByText(/Held-out validation is unavailable for this run/)).toBeVisible();
  await page.getByRole("button", { name: "Grid Event Monitor", exact: true }).click();
  await expect(page.getByTestId("event-interval-row")).toHaveCount(result.telemetry.event_time_series.length);
  await page.getByRole("button", { name: "RecoveryGuard", exact: true }).click();
  await expect(page.getByTestId("recovery-interval-row")).toHaveCount(48);
  await expect(page.locator(".simulation-metric").filter({ hasText: "SoC target" })).toContainText("Met");
  await expect(page.locator(".simulation-metric").filter({ hasText: "Work deadline" })).toContainText("Cleared");
  await page.screenshot({ path: test.info().outputPath("rafc-recovery.png"), fullPage: true });
});

test("insufficient calibration is displayed as unconfirmed", async ({ page }) => {
  await page.getByLabel("Reliability target").selectOption("99");
  await page.getByLabel("Calibration scenarios").fill("100");
  await page.getByRole("button", { name: "Assess Commitment", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recovery-aware commitment assessment" })).toBeVisible();
  await expect(page.getByText("unconfirmed", { exact: true })).toBeVisible();
  await expect(page.getByText(/Held-out validation: unavailable/)).toBeVisible();
});

test("event delivery does not mask recovery infeasibility", async ({ page }) => {
  await page.getByLabel("Recovery grid ceiling (MW)").fill("17");
  await page.getByRole("button", { name: "Run Simulation", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Nominal Simulation Results" })).toBeVisible();
  await page.getByRole("button", { name: "RecoveryGuard", exact: true }).click();
  await expect(page.getByText(/^Recovery infeasible:/)).toBeVisible();
  await expect(page.getByTestId("recovery-interval-row")).toHaveCount(0);
  await page.getByRole("button", { name: "Verification Portal", exact: true }).click();
  await expect(page.getByTestId("verification-overall").locator("strong")).toHaveText("fail");
});

test("benchmark page reads the three controllers from the recorded summary API", async ({ page }) => {
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/benchmarks/closed-loop"));
  await page.getByRole("button", {name: "Benchmarking", exact: true}).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.summary.results).toHaveLength(3);
  await expect(page.getByRole("heading", {name: "Benchmarking", exact: true})).toBeVisible();
  await expect(page.getByRole("row", {name: /fixed_horizon/})).toBeVisible();
  await expect(page.getByRole("row", {name: /rolling_risk_aware_mpc/})).toBeVisible();
  await expect(page.getByRole("row", {name: /rolling_rafc_v/})).toBeVisible();
  await expect(page.getByText(/A zero difference does not establish superiority/)).toBeVisible();
});

test("a persisted run can be reopened from database-backed history", async ({page}) => {
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/scenarios/run"));
  await page.getByRole("button", {name: "Run Simulation", exact: true}).click();
  const body = await (await responsePromise).json();
  expect(body.storage_status).toBe("persisted");
  await page.getByRole("button", {name: "Run History", exact: true}).click();
  const row = page.getByRole("row", {name: new RegExp(body.result.run_id)});
  await expect(row).toBeVisible();
  await row.getByRole("button", {name: "Open run"}).click();
  await expect(page.getByRole("button", {name: "Grid Event Monitor", exact: true})).toHaveClass(/active/);
  await expect(page.getByTestId("event-interval-row")).toHaveCount(12);
});
