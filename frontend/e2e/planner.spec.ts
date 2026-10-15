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
  const { result, reliability_certified } = await response.json();
  expect(reliability_certified).toBe(false);
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
