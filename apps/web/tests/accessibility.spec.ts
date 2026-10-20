import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loginAs } from "./support";

const pages = ["/", "/resolution", "/approvals", "/evaluation", "/anomalies", "/customers"];

for (const path of pages) {
  test(`${path} has no serious or critical automated WCAG violations`, async ({ page }) => {
    await loginAs(page, "admin", path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const material = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );
    expect(material, JSON.stringify(material, null, 2)).toEqual([]);
  });
}
