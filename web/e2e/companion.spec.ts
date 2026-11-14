import { test, expect, Page, APIRequestContext } from "@playwright/test";
import { createHash, randomBytes } from "node:crypto";
import { createServer, Server } from "node:http";
import { once } from "node:events";

const memberPassword = "synthetic browser member password";
async function login(
  page: Page,
  path = "/companion",
  username = "member_fixture",
  password = memberPassword,
) {
  await page.goto(path);
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
async function pending(api: APIRequestContext, name: string) {
  const verifier = randomBytes(48).toString("base64url"),
    state = randomBytes(32).toString("base64url");
  let received!: (uri: URL) => void;
  const returned = new Promise<URL>((resolve) => (received = resolve));
  const listener = createServer((req, res) => {
    const uri = new URL(req.url || "/", `http://127.0.0.1`);
    if (uri.pathname === "/companion/callback") {
      received(uri);
      res.writeHead(200, {
        "Content-Type": "text/plain",
        "Cache-Control": "no-store",
      });
      res.end("Synthetic callback received.");
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  listener.listen(0, "127.0.0.1");
  await once(listener, "listening");
  const address = listener.address();
  if (!address || typeof address === "string")
    throw new Error("No test loopback port");
  const redirect = `http://127.0.0.1:${address.port}/companion/callback`;
  const reply = await api.post("/api/v1/companion/authorizations", {
    data: {
      client_id: "twichui-market-companion",
      redirect_uri: redirect,
      state,
      code_challenge: createHash("sha256").update(verifier).digest("base64url"),
      code_challenge_method: "S256",
      device_name: name,
      platform: "Windows",
      app_version: "2.0.0-beta.1",
    },
  });
  expect(reply.status()).toBe(201);
  return {
    verifier,
    state,
    redirect,
    listener,
    returned,
    ...(await reply.json()),
  };
}
async function close(listener: Server) {
  await new Promise<void>((resolve) => listener.close(() => resolve()));
}
async function tokens(
  api: APIRequestContext,
  connection: Awaited<ReturnType<typeof pending>>,
  code: string,
) {
  const reply = await api.post("/api/v1/companion/token", {
    form: {
      grant_type: "authorization_code",
      client_id: "twichui-market-companion",
      code,
      code_verifier: connection.verifier,
      state: connection.state,
      redirect_uri: connection.redirect,
    },
  });
  expect(reply.status()).toBe(200);
  return reply.json();
}
test.beforeAll(() => {
  expect(new URL(process.env.BASE_URL || "http://proxy").hostname).toBe(
    "proxy",
  );
});

test("setup resumes after refresh and sign-in without claiming installation from a download", async ({
  page,
}) => {
  await login(page);
  await expect(
    page.getByRole("heading", {
      name: "Your market, ready on your PC.",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Release verification is in progress.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download for Windows" }),
  ).toHaveCount(0);
  await page.locator(".companion-steps button").nth(2).click();
  await expect(
    page.getByText("Waiting for a companion connection.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator(".companion-steps button").nth(2)).toHaveAttribute(
    "aria-current",
    "step",
  );
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("Username", { exact: true }).fill("member_fixture");
  await page.getByLabel("Password", { exact: true }).fill(memberPassword);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".companion-steps button").nth(2)).toHaveAttribute(
    "aria-current",
    "step",
  );
  await expect(
    page.getByText("Waiting for a companion connection.", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("system-browser approval route survives login, delivers a one-use code and supports owned rename/revoke", async ({
  page,
}) => {
  const connection = await pending(
    page.request,
    "Browser protocol Windows fixture",
  );
  const loaded: string[] = [];
  page.on("request", (request) => {
    if (request.resourceType() === "script") loaded.push(request.url());
  });
  try {
    await login(page, `/companion/authorize?request=${connection.request_id}`);
    await expect(
      page.getByRole("heading", {
        name: "Connect your companion.",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: "Browser protocol Windows fixture",
        exact: true,
      }),
    ).toBeVisible();
    expect(loaded.some((url) => /chart-engine|research-/.test(url))).toBe(
      false,
    );
    await page
      .getByRole("button", { name: "Approve this device", exact: true })
      .click();
    const callback = await connection.returned;
    expect(callback.searchParams.get("state")).toBe(connection.state);
    const code = callback.searchParams.get("code")!;
    expect(code).toBeTruthy();
    const grant = await tokens(page.request, connection, code);
    const replay = await page.request.post("/api/v1/companion/token", {
      form: {
        grant_type: "authorization_code",
        client_id: "twichui-market-companion",
        code,
        code_verifier: connection.verifier,
        state: connection.state,
        redirect_uri: connection.redirect,
      },
    });
    expect(replay.status()).toBe(400);
    await page.goto("/companion");
    await page.locator(".companion-steps button").nth(3).click();
    await expect(
      page.getByText("Waiting for first sync", { exact: true }),
    ).toBeVisible();
    const headers = { Authorization: `Bearer ${grant.access_token}` };
    const first = await (
      await page.request.get("/api/v1/sync/markets/1?limit=1", { headers })
    ).json();
    expect(first.has_more).toBe(true);
    const before = await (
      await page.request.get("/api/v1/companion/devices")
    ).json();
    expect(
      before.devices.find((row: { id: number }) => row.id === grant.device.id)
        .last_sync_at,
    ).toBeNull();
    const final = await page.request.get("/api/v1/sync/markets/1", {
      headers,
      params: { cursor: first.cursor, limit: 100 },
    });
    expect(final.status()).toBe(200);
    expect((await final.json()).has_more).toBe(false);
    await page
      .getByRole("button", { name: "Check sync status", exact: true })
      .click();
    await expect(
      page.getByText("Browser protocol Windows fixture is connected.", {
        exact: true,
      }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Account & devices", exact: true })
      .click();
    let card = page.getByRole("article", {
      name: "Browser protocol Windows fixture device",
      exact: true,
    });
    await card.getByRole("button", { name: "Rename", exact: true }).click();
    await card
      .getByLabel("New name for Browser protocol Windows fixture", {
        exact: true,
      })
      .fill("Renamed Windows fixture");
    await card.getByRole("button", { name: "Save name", exact: true }).click();
    card = page.getByRole("article", {
      name: "Renamed Windows fixture device",
      exact: true,
    });
    await expect(card).toBeVisible();
    await expect(page.locator("body")).not.toContainText(grant.access_token);
    await expect(page.locator("body")).not.toContainText(grant.refresh_token);
    expect(
      (await page.request.get("/api/v1/auth/me", { headers })).status(),
    ).toBe(200);
    await card
      .getByRole("button", { name: "Revoke access", exact: true })
      .click();
    await card
      .getByRole("button", {
        name: "Revoke Renamed Windows fixture",
        exact: true,
      })
      .click();
    await expect(card.getByText("Revoked", { exact: true })).toBeVisible();
    expect(
      (await page.request.get("/api/v1/sync/markets/1", { headers })).status(),
    ).toBe(401);
  } finally {
    await close(connection.listener);
  }
});

test("denial returns only the bound error and creates no device", async ({
  page,
}) => {
  const connection = await pending(page.request, "Declined Windows fixture");
  try {
    await login(page, `/companion/authorize?request=${connection.request_id}`);
    await page.getByRole("button", { name: "Deny", exact: true }).click();
    const callback = await connection.returned;
    expect(callback.searchParams.get("error")).toBe("access_denied");
    expect(callback.searchParams.get("state")).toBe(connection.state);
    expect(callback.searchParams.has("code")).toBe(false);
    const profiles = await (
      await page.request.get("/api/v1/companion/devices")
    ).json();
    expect(
      profiles.devices.some(
        (row: { name: string }) => row.name === "Declined Windows fixture",
      ),
    ).toBe(false);
  } finally {
    await close(connection.listener);
  }
});

test("an account-cookie change invalidates the displayed consent and reload restores the correct account", async ({
  page,
}) => {
  const connection = await pending(
    page.request,
    "Account switch Windows fixture",
  );
  try {
    await login(page, `/companion/authorize?request=${connection.request_id}`);
    await expect(
      page.getByRole("button", { name: "Approve this device", exact: true }),
    ).toBeVisible();
    const switched = await page.request.post("/api/v1/auth/login", {
      data: {
        username: "prefs_isolation_a",
        password: "synthetic preferences password",
      },
    });
    expect(switched.status()).toBe(200);
    await page
      .getByRole("button", { name: "Approve this device", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText("CSRF token required");
    await page
      .getByRole("button", { name: "Reload approval page", exact: true })
      .click();
    await expect(page.locator(".consent-account strong")).toHaveText(
      "prefs_isolation_a",
    );
    await page.getByRole("button", { name: "Deny", exact: true }).click();
    expect((await connection.returned).searchParams.get("error")).toBe(
      "access_denied",
    );
  } finally {
    await close(connection.listener);
  }
});

test("expired approvals explain how to restart without inventing a successful connection", async ({
  page,
}) => {
  await login(page, `/companion/authorize?request=${"E".repeat(43)}`);
  await expect(page.getByRole("alert")).toContainText(
    "Connection request expired",
  );
  await expect(
    page.getByRole("button", { name: "Approve this device", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText(
      "Expired or cancelled requests must be restarted in the companion.",
      { exact: true },
    ),
  ).toBeVisible();
});

test("device ownership stays private while administrators can inspect and revoke native access", async ({
  page,
  playwright,
  browser,
}) => {
  const member = await playwright.request.newContext({
    baseURL: "http://proxy",
  });
  const loginReply = await member.post("/api/v1/auth/login", {
    data: { username: "member_fixture", password: memberPassword },
  });
  expect(loginReply.status()).toBe(200);
  const csrf = (await loginReply.json()).csrf_token;
  const connection = await pending(member, "Administrator inspection fixture");
  try {
    const details = await (
      await member.get(
        `/api/v1/companion/authorizations/${connection.request_id}`,
      )
    ).json();
    const approved = await member.post(
      `/api/v1/companion/authorizations/${connection.request_id}/decision`,
      {
        headers: { "x-csrf-token": csrf },
        data: { decision: "approve", consent_token: details.consent_token },
      },
    );
    expect(approved.status()).toBe(200);
    const code = new URL((await approved.json()).redirect_uri).searchParams.get(
      "code",
    )!;
    const grant = await tokens(member, connection, code);
    const other = await browser.newContext({ baseURL: "http://proxy" });
    try {
      const otherPage = await other.newPage();
      await login(
        otherPage,
        "/account",
        "prefs_isolation_b",
        "synthetic preferences password",
      );
      await expect(
        otherPage.getByRole("heading", {
          name: "Your desktop companions",
          exact: true,
        }),
      ).toBeVisible();
      await expect(otherPage.locator("body")).not.toContainText(
        "Administrator inspection fixture",
      );
    } finally {
      await other.close();
    }
    await login(
      page,
      "/administration",
      "owner",
      "synthetic browser owner password",
    );
    await page.getByRole("tab", { name: "Devices", exact: true }).click();
    const card = page.getByRole("article", {
      name: "Administrator inspection fixture device",
      exact: true,
    });
    await expect(card).toBeVisible();
    await expect(card).toContainText("member_fixture");
    await expect(
      card.getByRole("button", { name: "Rename", exact: true }),
    ).toHaveCount(0);
    await card
      .getByRole("button", { name: "Revoke access", exact: true })
      .click();
    await card
      .getByRole("button", {
        name: "Revoke Administrator inspection fixture",
        exact: true,
      })
      .click();
    await expect(card.getByText("Revoked", { exact: true })).toBeVisible();
    expect(
      (
        await member.get("/api/v1/sync/markets/1", {
          headers: { Authorization: `Bearer ${grant.access_token}` },
        })
      ).status(),
    ).toBe(401);
  } finally {
    await close(connection.listener);
    await member.dispose();
  }
});
