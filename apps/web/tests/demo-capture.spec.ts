import { expect, test } from "@playwright/test";
import { loginAs } from "./support";

const views = [
  ["overview", "/", "Customer operations that resolve. Not just respond."],
  ["customer-360", "/customers", "Customer 360"],
  ["resolution", "/resolution", "Resolution workspace"],
  ["trace-explorer", "/traces", "Trace explorer"],
  ["evaluation-lab", "/evaluation", "Evaluation lab"],
  ["system-health", "/health", "System health"],
] as const;

test("capture the faculty-demo workflow", async ({ page }) => {
  await loginAs(page, "admin");
  for (const [name, path, heading] of views) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await page.screenshot({ path: `../../artifacts/demo/${name}.png`, fullPage: true });
  }
});
