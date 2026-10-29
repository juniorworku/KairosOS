import {
  test as base,
  expect,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { DateTime } from "luxon";
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
    await page.getByRole("link", { name: "Goals", exact: true }).click();
    const running = page.getByRole("complementary", {
      name: "Current focus session",
    });
    await expect(running).toContainText(actionTitle);
    await running.getByRole("link", { name: "Return to session" }).click();
    await expect(
      page.getByRole("button", { name: "End session" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "End session" }).click();
    await page.getByRole("button", { name: "4", exact: true }).click();
    await page.getByRole("button", { name: "Save session" }).click();
    await expect(page.getByText("4 / 5", { exact: true })).toBeVisible();
    await page.getByLabel("Books (books)", { exact: true }).fill("3");
    await page
      .getByRole("button", { name: "Log progress", exact: true })
      .click();
    await expect(
      page.getByText("Progress saved", { exact: true }),
    ).toBeVisible();
    const progress = (await (
      await page.request.get(`/api/v1/goals/${goalId}`)
    ).json()) as { checkins: { metric_value: number }[] };
    expect(progress.checkins.at(-1)?.metric_value).toBe(3);
    await page
      .getByRole("link", { name: "Review this week", exact: true })
      .click();
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
  await page.goto("/plan");
  await expect(
    page.getByRole("heading", { name: "Plan", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".fc-col-header-cell")).toHaveCount(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const calendarAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(calendarAccessibility.violations).toEqual([]);
  const timedScroller = page.locator(".fc-scroller-liquid-absolute");
  await page.locator('.fc-timegrid-col[role="gridcell"]').first().focus();
  const offset = await timedScroller.evaluate((element) => element.scrollTop);
  await page.keyboard.press(offset > 0 ? "PageUp" : "PageDown");
  await expect
    .poll(() => timedScroller.evaluate((element) => element.scrollTop))
    .not.toBe(offset);
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
  const workerAsset = await page.request.get("/sw.js");
  test.skip(
    !workerAsset.ok() ||
      !workerAsset.headers()["content-type"]?.includes("javascript"),
    "Offline reload requires the production build; dev mode has no service worker.",
  );
  await expect
    .poll(
      async () =>
        page.evaluate(
          async () => !!(await navigator.serviceWorker?.getRegistration()),
        ),
      { timeout: 15000 },
    )
    .toBe(true);
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

test("tasks, recurring events, notes, and occurrence edits persist", async ({
  page,
}) => {
  test.setTimeout(90000);
  const title = `E2E agenda ${Date.now()}`;
  let taskId = "";
  let eventId = "";
  await page.goto("/plan");
  const me = (await (await page.request.get("/api/v1/me")).json()) as {
    timezone: string;
  };
  const monday = DateTime.now()
    .setZone(me.timezone)
    .startOf("week")
    .plus({ weeks: 1 });
  try {
    await page.getByRole("button", { name: "Next week", exact: true }).click();
    await page.getByRole("button", { name: "Add task", exact: true }).click();
    let dialog = page.getByRole("dialog");
    await dialog.getByLabel("Title", { exact: true }).fill(title);
    await dialog
      .getByLabel("Notes", { exact: true })
      .fill("Take the notebook.");
    await dialog
      .getByLabel("Due date", { exact: true })
      .fill(DateTime.now().setZone(me.timezone).toISODate()!);
    await dialog
      .getByRole("button", { name: "Save task", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    const tasks = (await (await page.request.get("/api/v1/tasks")).json()) as {
      id: string;
      title: string;
    }[];
    taskId = tasks.find((task) => task.title === title)!.id;
    await page.getByRole("link", { name: "Today", exact: true }).click();
    await page.getByRole("link").filter({ hasText: title }).click();
    await expect(page).toHaveURL(new RegExp(`task=${taskId}`));
    const linkedTask = page.locator(`#agenda-task-${taskId}`);
    await expect(linkedTask).toBeFocused();
    await expect(linkedTask).toHaveClass(/is-context-task/);
    await page.getByRole("button", { name: "Next week", exact: true }).click();
    await page
      .getByRole("button", { name: `Schedule task: ${title}`, exact: true })
      .click();
    dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("Start", { exact: true })
      .fill(monday.set({ hour: 14 }).toFormat("yyyy-MM-dd'T'HH:mm"));
    await dialog
      .getByLabel("End", { exact: true })
      .fill(monday.set({ hour: 15 }).toFormat("yyyy-MM-dd'T'HH:mm"));
    await dialog.getByLabel("Repeat", { exact: true }).check();
    await dialog
      .getByLabel("Frequency", { exact: true })
      .selectOption("weekly");
    for (const weekday of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
      await dialog
        .getByLabel(weekday, { exact: true })
        .setChecked(weekday === "Mon");
    await dialog.getByLabel("Number of occurrences", { exact: true }).fill("3");
    await dialog
      .getByRole("button", { name: "Save event", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    const events = (await (
      await page.request.get("/api/v1/events")
    ).json()) as {
      id: string;
      title: string;
      recurrence: { count: number };
      notes: string;
    }[];
    const created = events.find((event) => event.title === title)!;
    eventId = created.id;
    expect(created.notes).toBe("Take the notebook.");
    expect(created.recurrence.count).toBe(3);
    await page.getByRole("button", { name: "List", exact: true }).click();
    await page
      .getByRole("region", { name: "Calendar", exact: true })
      .getByRole("button")
      .filter({ hasText: title })
      .click();
    dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("button", { name: "This occurrence", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await dialog
      .getByLabel("Notes", { exact: true })
      .fill("Only this meeting needs the printed draft.");
    await dialog
      .getByRole("button", { name: "Save event", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    const end = monday.plus({ weeks: 3 }).toISODate();
    const feed = (await (
      await page.request.get(
        `/api/v1/agenda?start=${monday.toISODate()}&end=${end}`,
      )
    ).json()) as { source_id: string; notes: string }[];
    const occurrences = feed.filter((item) => item.source_id === eventId);
    expect(occurrences).toHaveLength(3);
    expect(
      occurrences.filter(
        (item) => item.notes === "Only this meeting needs the printed draft.",
      ),
    ).toHaveLength(1);
    await page
      .getByRole("button", { name: `Mark done: ${title}`, exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: `Mark done: ${title}`, exact: true }),
    ).toHaveCount(0);
    await page.reload();
    await page.getByText("Completed tasks", { exact: true }).click();
    await expect(
      page.getByRole("button", { name: `Mark to do: ${title}`, exact: true }),
    ).toBeVisible();
  } finally {
    if (eventId)
      await write(page, `/events/${eventId}`, undefined, "DELETE").catch(
        () => {},
      );
    if (taskId)
      await write(page, `/tasks/${taskId}`, undefined, "DELETE").catch(
        () => {},
      );
  }
});

test("manual action creation and proposed moves require explicit acceptance", async ({
  page,
}) => {
  test.setTimeout(90000);
  const title = `E2E manual ${Date.now()}`;
  let goalId = "";
  await page.goto("/plan");
  const me = (await (await page.request.get("/api/v1/me")).json()) as {
    timezone: string;
    work_days: number[];
    work_start: string;
    work_end: string;
  };
  const monday = DateTime.now()
    .setZone(me.timezone)
    .startOf("week")
    .plus({ weeks: 1 });
  const workday = monday.plus({ days: me.work_days[0] });
  const [hour, minute] = me.work_start.split(":").map(Number);
  const start = workday.set({ hour, minute });
  const target = start.plus({ hours: 2 });
  try {
    const goal = (await write(page, "/goals", {
      title,
      outcome_statement: "Test manual scheduling",
      start_date: DateTime.now().setZone(me.timezone).toISODate(),
      target_date: monday.plus({ days: 60 }).toISODate(),
      actions: [{ title, weekly_minutes_target: 60 }],
    })) as { id: string; actions: { id: string }[] };
    goalId = goal.id;
    await page.reload();
    await page.getByRole("button", { name: "Next week", exact: true }).click();
    await page
      .getByRole("button", { name: "Schedule action", exact: true })
      .click();
    let dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("Choose a goal", { exact: true })
      .selectOption(goal.id);
    await dialog
      .getByLabel("Choose an action", { exact: true })
      .selectOption(goal.actions[0].id);
    await dialog
      .getByLabel("Start", { exact: true })
      .fill(start.toFormat("yyyy-MM-dd'T'HH:mm"));
    await dialog
      .getByLabel("End", { exact: true })
      .fill(start.plus({ hours: 1 }).toFormat("yyyy-MM-dd'T'HH:mm"));
    await dialog
      .getByLabel("Notes", { exact: true })
      .fill("Manual block notes");
    await dialog
      .getByRole("button", { name: "Schedule action", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    await page.getByRole("button", { name: "List", exact: true }).click();
    await page
      .getByRole("region", { name: "Calendar", exact: true })
      .getByRole("button")
      .filter({ hasText: title })
      .click();
    dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("Notes", { exact: true })).toHaveValue(
      "Manual block notes",
    );
    await dialog
      .getByLabel("Start", { exact: true })
      .fill(target.toFormat("yyyy-MM-dd'T'HH:mm"));
    await dialog
      .getByLabel("End", { exact: true })
      .fill(target.plus({ hours: 1 }).toFormat("yyyy-MM-dd'T'HH:mm"));
    await dialog
      .getByRole("button", { name: "Propose move", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Review draft", exact: true }),
    ).toBeVisible();
    let blocks = (await (
      await page.request.get(`/api/v1/plan/week?start=${monday.toISODate()}`)
    ).json()) as { goal_id: string; start_at: string; notes: string }[];
    expect(
      DateTime.fromISO(
        blocks.find((block) => block.goal_id === goalId)!.start_at,
      ).toMillis(),
    ).toBe(start.toMillis());
    await page
      .getByRole("button", { name: "Keep change", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Review draft", exact: true }),
    ).toHaveCount(0);
    blocks = (await (
      await page.request.get(`/api/v1/plan/week?start=${monday.toISODate()}`)
    ).json()) as { goal_id: string; start_at: string; notes: string }[];
    expect(
      DateTime.fromISO(
        blocks.find((block) => block.goal_id === goalId)!.start_at,
      ).toMillis(),
    ).toBe(target.toMillis());
    expect(blocks.find((block) => block.goal_id === goalId)!.notes).toBe(
      "Manual block notes",
    );
  } finally {
    if (goalId)
      await write(page, `/goals/${goalId}`, undefined, "DELETE").catch(
        () => {},
      );
  }
});

test("connected workspace routes retain dates and remain accessible in both themes", async ({
  page,
}) => {
  test.setTimeout(90000);
  for (const theme of ["dark", "light"]) {
    await page.goto("/settings");
    await page.getByLabel("Theme", { exact: true }).selectOption(theme);
    for (const route of [
      "/today",
      "/goals",
      "/focus",
      "/review",
      "/coach",
      "/plan?date=2026-11-04",
    ]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      if (route.startsWith("/plan")) {
        await expect(
          page.getByLabel("Selected date", { exact: true }),
        ).toHaveValue("2026-11-04");
        await page.reload();
        await expect(
          page.getByLabel("Selected date", { exact: true }),
        ).toHaveValue("2026-11-04");
      }
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        )
        .toBe(true);
      const audit = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      expect(audit.violations, `${theme} ${route}`).toEqual([]);
    }
  }
});

test("monthly and yearly repeats persist from the event form", async ({
  page,
}) => {
  test.setTimeout(60000);
  await page.goto("/plan?date=2027-01-31");
  for (const frequency of ["monthly", "yearly"]) {
    const title = `E2E ${frequency} ${Date.now()}`;
    let eventId = "";
    try {
      await page
        .getByRole("button", { name: "Add event", exact: true })
        .click();
      const dialog = page.getByRole("dialog");
      await dialog.getByLabel("Title", { exact: true }).fill(title);
      await dialog
        .getByLabel("Start", { exact: true })
        .fill("2027-01-31T09:00");
      await dialog.getByLabel("End", { exact: true }).fill("2027-01-31T10:00");
      await dialog.getByLabel("Time zone", { exact: true }).fill("UTC");
      await dialog.getByLabel("Repeat", { exact: true }).check();
      await dialog
        .getByLabel("Frequency", { exact: true })
        .selectOption(frequency);
      const response = page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/v1/events") && r.request().method() === "POST",
      );
      await dialog
        .getByRole("button", { name: "Save event", exact: true })
        .click();
      const saved = await response;
      expect(saved.status()).toBe(201);
      eventId = ((await saved.json()) as { id: string }).id;
      await expect(dialog).toHaveCount(0);
      await page.reload();
      const event = (await (
        await page.request.get(`/api/v1/events/${eventId}`)
      ).json()) as { recurrence: { frequency: string } };
      expect(event.recurrence.frequency).toBe(frequency);
    } finally {
      if (eventId) await write(page, `/events/${eventId}`, undefined, "DELETE");
    }
  }
});

test("visible light and dark controls persist on desktop and mobile", async ({
  page,
}) => {
  await page.goto("/today");
  const desktop = page.locator(".sidebar");
  await desktop
    .getByRole("button", { name: "Dark theme", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await desktop
    .getByRole("button", { name: "Light theme", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .locator(".mobile-bar")
    .getByRole("button", { name: "Dark theme", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog", { name: "Kairos", exact: true })
    .getByRole("button", { name: "Light theme", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Close navigation" }).click();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});

test("native setup is reachable from focus without installing or enabling the helper", async ({
  page,
}) => {
  await page.goto("/focus");
  await page
    .getByRole("link", { name: "Set up native blocking", exact: true })
    .click();
  await expect(page).toHaveURL(/\/settings#native-blocking$/);
  const panel = page.locator("#native-blocking");
  await expect(panel).toBeFocused();
  await panel.getByText("Linux setup", { exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "Pair Linux companion", exact: true }),
  ).toBeVisible();
  await expect(panel).toContainText(
    "The web app cannot change your local executable list or enable the helper.",
  );
  const audit = await new AxeBuilder({ page })
    .include("#native-blocking")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(audit.violations).toEqual([]);
});
