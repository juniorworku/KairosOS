import {
  test as base,
  expect,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile, writeFile } from "node:fs/promises";
type State = Awaited<ReturnType<BrowserContext["storageState"]>>;
const test = base.extend<object, { signedIn: State }>({
  signedIn: [
    async ({ browser }, provide) => {
      const baseURL =
        process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173";
      const context = await browser.newContext({ baseURL });
      const page = await context.newPage();
      const statePath = "/tmp/kairos-e2e-session.json";
      let reused = false;
      try {
        const saved = JSON.parse(await readFile(statePath, "utf8")) as State;
        await context.addCookies(saved.cookies);
        reused = (await context.request.get("/api/v1/me")).ok();
      } catch {
        /* A fresh local sign-in follows. */
      }
      if (!reused) {
        await context.clearCookies();
        await page.goto("/welcome");
        const config = (await (
          await page.request.get("/api/v1/auth/config")
        ).json()) as { development_owner_email?: string };
        expect(
          config.development_owner_email,
          "Run E2E only against the local dev stack",
        ).toBeTruthy();
        const start = Date.now();
        await page
          .getByLabel("Email", { exact: true })
          .fill(config.development_owner_email!);
        await page.getByRole("button", { name: "Send sign-in link" }).click();
        await expect(
          page.getByRole("heading", { name: "Check your email" }),
        ).toBeVisible();
        let link = "";
        await expect
          .poll(
            async () => {
              const inbox = (await (
                await page.request.get("http://localhost:8025/api/v1/messages")
              ).json()) as {
                messages: {
                  ID: string;
                  Created: string;
                  To: { Address: string }[];
                }[];
              };
              const message = inbox.messages.find(
                (m) =>
                  m.To.some(
                    (to) => to.Address === config.development_owner_email,
                  ) && Date.parse(m.Created) >= start - 1000,
              );
              if (!message) return false;
              const detail = (await (
                await page.request.get(
                  `http://localhost:8025/api/v1/message/${message.ID}`,
                )
              ).json()) as { Text: string };
              link =
                detail.Text.match(
                  /https?:\/\/[^\s]+\/auth\/confirm\?token=[A-Za-z0-9_-]+/,
                )?.[0] || "";
              return !!link;
            },
            { timeout: 30000 },
          )
          .toBe(true);
        const confirm = new URL(link);
        await page.goto(`${confirm.pathname}${confirm.search}`);
        await page.getByRole("button", { name: "Sign in to Kairos" }).click();
        await expect(
          page.getByRole("heading", { name: "Today", exact: true }),
        ).toBeVisible();
      }
      const state = await context.storageState();
      await writeFile(statePath, JSON.stringify(state), { mode: 0o600 });
      await provide(state);
      await context.close();
    },
    { scope: "worker" },
  ],
  storageState: async ({ signedIn }, provide) => provide(signedIn),
});
async function write(
  page: Page,
  path: string,
  body?: unknown,
  method = "POST",
) {
  const csrf = (await (await page.request.get("/api/v1/auth/csrf")).json()) as {
    csrf_token: string;
  };
  const response = await page.request.fetch(`/api/v1${path}`, {
    method,
    headers: {
      "X-CSRF-Token": csrf.csrf_token,
      Origin: new URL(page.url()).origin,
    },
    ...(body === undefined ? {} : { data: body }),
  });
  expect(response.ok(), `${method} ${path}: ${response.status()}`).toBe(true);
  return response.status() === 204 ? null : response.json();
}
function day(offset = 0) {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

test("goal, weekly draft, focus, check-in, review, and settings", async ({
  page,
}) => {
  test.setTimeout(90000);
  const title = `E2E reading ${Date.now()}`;
  const actionTitle = `Read notes ${Date.now()}`;
  let goalId = "";
  await page.goto("/today");
  await page.getByRole("link", { name: "Add a goal", exact: true }).click();
  await page.getByLabel("Goal", { exact: true }).fill(title);
  await page
    .getByLabel("What will be different?")
    .fill("Read and summarize twelve books.");
  await page.getByLabel("Measure", { exact: true }).fill("Books");
  await page.getByLabel("Unit", { exact: true }).fill("books");
  await page.getByLabel("Target value", { exact: true }).fill("12");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page
    .getByLabel("Why does this matter?")
    .fill("Make regular time for reading.");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("What do you want to protect?").fill("Family evenings");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("What will you do?").fill(actionTitle);
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Add if-then plan" }).click();
  await page
    .getByLabel("Obstacle", { exact: true })
    .fill("Phone notifications");
  await page.getByLabel("If this happens…").fill("I reach for my phone");
  await page.getByLabel("Then I will…").fill("Put it in the next room");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Save goal" }).click();
  await expect(
    page.getByRole("heading", { name: "Goals", exact: true }),
  ).toBeVisible();
  await page.getByRole("link").filter({ hasText: title }).click();
  goalId = page.url().split("/").pop()!;
  try {
    await page.getByLabel("Current value").fill("2");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByText("2 books", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "Plan", exact: true }).click();
    await page.getByRole("button", { name: "Next week", exact: true }).click();
    await page.getByRole("button", { name: "Draft week", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Accept remaining" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Accept remaining" }).click();
    await expect(
      page.getByRole("button", { name: "Accept remaining" }),
    ).toHaveCount(0);
    await page.getByRole("link", { name: "Focus", exact: true }).click();
    await test.step("choose focus action", async () => {
      await page
        .getByLabel("Action", { exact: true })
        .selectOption({ label: actionTitle });
    });
    await page.getByLabel("Minutes", { exact: true }).fill("25");
    await test.step("start focus", async () => {
      await page.getByRole("button", { name: "Start session" }).click();
      await expect(
        page.getByRole("button", { name: "End session" }),
      ).toBeVisible();
    });
    await expect(
      page.getByRole("button", { name: "End session" }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("button", { name: "End session" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "End session" }).click();
    await page.getByRole("button", { name: "4", exact: true }).click();
    await page.getByRole("button", { name: "Save session" }).click();
    await expect(page.getByText("4 / 5", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "Review", exact: true }).click();
    const reflection = (await (
      await page.request.get(
        `/api/v1/reflection/${await page.locator(".week-nav span").textContent()}`,
      )
    ).json()) as {
      wins?: string;
      misses?: string;
      adjustments?: string;
    } | null;
    await page
      .getByLabel("What went well?")
      .fill("Finished the reading session.");
    await page.getByRole("button", { name: "Save review" }).click();
    await expect(page.getByText("Saved", { exact: true })).toBeVisible();
    const week = (await page.locator(".week-nav span").textContent())!;
    await write(page, `/reflection/${week}`, {
      wins: reflection?.wins || "",
      misses: reflection?.misses || "",
      adjustments: reflection?.adjustments || "",
    });
    await page.getByRole("link", { name: "Settings", exact: true }).click();
    await page.getByLabel("Theme", { exact: true }).selectOption("dark");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByLabel("Theme", { exact: true }).selectOption("system");
  } finally {
    if (goalId)
      await write(page, `/goals/${goalId}`, undefined, "DELETE").catch(
        () => {},
      );
  }
});

test("mobile navigation and accessibility", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/today");
  await expect(
    page.getByRole("heading", { name: "Today", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Goals", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Goals", exact: true }),
  ).toBeVisible();
});

test("installed shell reloads offline and replays a check-in once", async ({
  page,
  context,
}) => {
  test.setTimeout(60000);
  await page.goto("/today");
  await expect(
    page.getByRole("heading", { name: "Today", exact: true }),
  ).toBeVisible();
  const hasWorker = await page.evaluate(
    async () => !!(await navigator.serviceWorker?.getRegistration()),
  );
  test.skip(
    !hasWorker,
    "Offline reload requires the production build; dev mode has no service worker.",
  );
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  const goal = (await write(page, "/goals", {
    title: `Offline test ${Date.now()}`,
    metric_name: "Chapters",
    metric_unit: "chapters",
    metric_start: 0,
    metric_target: 10,
    start_date: day(),
    target_date: day(84),
    actions: [{ title: "Read", weekly_minutes_target: 60 }],
  })) as { id: string };
  try {
    await page.goto(`/goals/${goal.id}`);
    await expect(page.getByLabel("Current value")).toBeVisible();
    await context.setOffline(true);
    await page.getByLabel("Current value").fill("4");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(
      page.getByText("Saved on this device. Will sync when connected."),
    ).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      /^Offline test/,
    );
    await expect(
      page.getByText(/Offline. Saved data is available/),
    ).toBeVisible();
    await context.setOffline(false);
    await expect(page.getByText("4 chapters", { exact: true })).toBeVisible();
    await page.reload();
    const saved = (await (
      await page.request.get(`/api/v1/goals/${goal.id}`)
    ).json()) as { checkins: { metric_value: number }[] };
    expect(saved.checkins.filter((c) => c.metric_value === 4)).toHaveLength(1);
  } finally {
    await context.setOffline(false);
    await write(page, `/goals/${goal.id}`, undefined, "DELETE");
  }
});
