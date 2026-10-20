import { expect, type Page } from "@playwright/test";

const identities = ["customer", "agent", "supervisor", "admin"] as const;
type Identity = (typeof identities)[number];

export async function tokenFor(identity: Identity): Promise<string> {
  const body = new URLSearchParams({
    grant_type: "password",
    client_id: "resolveai-api",
    username: identity,
    password: "resolveai-local",
    scope: "openid profile email",
  });
  const response = await fetch(
    "http://localhost:8080/realms/resolveai/protocol/openid-connect/token",
    { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body },
  );
  if (!response.ok) throw new Error(`Keycloak token request failed (${response.status})`);
  const payload = await response.json() as { access_token: string };
  return payload.access_token;
}

export async function loginAs(page: Page, identity: Identity, path = "/"): Promise<void> {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in with Keycloak" }).click();
  await page.getByLabel(/username|email/i).fill(identity);
  await page.getByLabel("Password", { exact: true }).fill("resolveai-local");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("button", { name: /sign out/i })).toBeVisible({ timeout: 120_000 });
  if (path !== "/") await page.goto(path);
}

export const apiUrl = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
export const orderId = "a1cb0753-9fab-5bfe-a70d-7ddb6845bd50";
export const paymentId = "86d8c584-7dc1-5fec-9bb0-d47556fcffcf";
