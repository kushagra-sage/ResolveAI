import { expect, test } from "@playwright/test";
import { apiUrl, loginAs, orderId, paymentId, tokenFor } from "./support";

test("customer resolution authenticates and returns a governed result", async ({ page }) => {
  await loginAs(page, "customer", "/resolution");
  await page.getByLabel("Customer request").fill("Where is my returned order?");
  await page.getByRole("button", { name: "Run governed resolution" }).click();
  await expect(page.locator(".message-bubble.ai")).toBeVisible();
  await expect(page.locator(".message-bubble.ai")).toContainText("ResolveAI");
});

test("agent creates an approval and a supervisor records a decision", async ({ page, request }) => {
  const created = await request.post(`${apiUrl}/v1/resolutions`, {
    headers: { Authorization: `Bearer ${await tokenFor("agent")}` },
    data: {
      message: "Refund ₹200 immediately",
      order_id: orderId,
      payment_id: paymentId,
      currency: "INR",
      reason_code: "browser_test",
    },
  });
  expect(created.ok()).toBeTruthy();
  const createdPayload = await created.json();
  expect(createdPayload.status).toBe("waiting_approval");

  await loginAs(page, "supervisor", "/approvals");
  const card = page.locator(".approval-card").filter({
    hasText: `Run ${createdPayload.run_id.slice(0, 8)}`,
  });
  await expect(card).toBeVisible();
  await card.getByLabel("Review reason").fill("Verified in browser workflow");
  await card.getByRole("button", { name: "Reject" }).click();
  await expect(card).toHaveCount(0);
});

test("trace and evaluation evidence pages render", async ({ page }) => {
  await loginAs(page, "supervisor", "/traces");
  await expect(page.getByRole("heading", { name: "Trace explorer" })).toBeVisible();
  await page.goto("/evaluation");
  await expect(page.getByRole("heading", { name: "Evaluation lab" })).toBeVisible();
});

test("CommerceOps loads tenant-scoped anomaly data", async ({ page }) => {
  await loginAs(page, "admin", "/anomalies");
  await expect(page.getByText("Live PostgreSQL")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Explainable anomalies" })).toBeVisible();
});

test("Customer 360 loads deterministic synthetic support data", async ({ page }) => {
  await loginAs(page, "agent", "/customers");
  await expect(page.getByText("Synthetic dataset active")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Customer and case workload" })).toBeVisible();
  await expect(page.getByText("Asha Mehta (Synthetic)")).toBeVisible();
  await expect(page.getByText("No real PII")).toBeVisible();
});

test("keyboard users can skip navigation and open command search", async ({ page, browserName }) => {
  await loginAs(page, "agent");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  if (browserName === "webkit") {
    // WebKit follows the macOS preference that excludes links from sequential Tab focus.
    await skipLink.focus();
  } else {
    await page.keyboard.press("Tab");
  }
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page.keyboard.press("Control+K");
  await expect(page.getByRole("dialog", { name: "Navigate workspace" })).toBeVisible();
});
