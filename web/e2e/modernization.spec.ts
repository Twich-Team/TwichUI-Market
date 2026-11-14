import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("owner");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic browser owner password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Market Explorer", exact: true }),
  ).toBeVisible();
}
async function accessible(page: Page, name: string) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  fs.mkdirSync("../artifacts/modernization", { recursive: true });
  fs.writeFileSync(
    `../artifacts/modernization/${name}-axe.json`,
    JSON.stringify(result.violations, null, 2),
  );
  expect(result.violations).toEqual([]);
}
test("catalogue variants, accessible item facts, chart controls and bounded history rendering", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 1440, height: 1050 });
  await login(page);
  const catalogue = page.getByRole("region", {
    name: "Item catalogue",
    exact: true,
  });
  await expect(catalogue.getByRole("status")).toHaveText("Page 1 of 2");
  await expect(catalogue.locator("tbody > tr")).toHaveCount(25);
  await catalogue
    .getByRole("button", { name: "Next items", exact: true })
    .click();
  await expect(catalogue.getByRole("status")).toHaveText("Page 2 of 2");
  await catalogue
    .getByRole("button", { name: "Previous items", exact: true })
    .click();
  await catalogue.getByRole("button", { name: "Supply", exact: false }).click();
  await expect(catalogue.locator('th[aria-sort="ascending"]')).toContainText(
    "Supply",
  );
  await catalogue.getByRole("button", { name: "ID", exact: false }).click();
  const blade = catalogue
    .getByRole("row")
    .filter({ hasText: "Synthetic Enchanted Blade" });
  await blade.getByRole("button", { name: /2 variants/ }).click();
  const variants = page.getByRole("table", {
    name: "Variants of Synthetic Enchanted Blade",
  });
  await expect(variants.locator("tbody tr")).toHaveCount(2);
  await expect(variants).toContainText("2g");
  await expect(variants).toContainText("3g");
  const item = catalogue.getByRole("button", {
    name: "Item details for Synthetic Arcane Crystal",
    exact: true,
  });
  await page.keyboard.press("Tab");
  await item.focus();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("+10 Fixture Strength");
  await expect(page.getByRole("dialog")).toContainText(
    "Asking-price ranges across variants",
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "10Y", exact: true }).click();
  await page.locator(".chart-viewport").first().scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("img", {
      name: "Observed asking-price history",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("60-day reference", { exact: true }).check();
  await page.getByLabel("Zoom start (%)").fill("20");
  await page.getByRole("button", { name: "Reset zoom", exact: true }).click();
  await expect(page.getByLabel("Zoom start (%)")).toHaveValue("0");
  await page.getByText("Read exact chart data", { exact: true }).click();
  await page.getByLabel("Virtual scrolling", { exact: false }).check();
  const virtual = page.getByRole("table", {
    name: "Virtual historical observations",
    exact: true,
  });
  await expect(virtual).toBeVisible();
  const virtualRows = await virtual.locator("tbody tr").count();
  expect(virtualRows).toBeLessThan(40);
  fs.mkdirSync("../artifacts/modernization", { recursive: true });
  fs.writeFileSync(
    "../artifacts/modernization/row-window-measurements.json",
    JSON.stringify(
      {
        synthetic: true,
        catalogue_rows: 25,
        calendar_days: 3651,
        virtual_rows: virtualRows,
        paginated_history_rows: 50,
      },
      null,
      2,
    ),
  );
  await page.getByLabel("Virtual scrolling", { exact: false }).uncheck();
  await expect(
    page
      .getByRole("table", {
        name: "Exact historical observations",
        exact: true,
      })
      .locator("tbody tr"),
  ).toHaveCount(50);
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  fs.mkdirSync("../artifacts/modernization", { recursive: true });
  fs.writeFileSync(
    "../artifacts/modernization/explorer-axe.json",
    JSON.stringify(axe.violations, null, 2),
  );
  expect(axe.violations).toEqual([]);
  await page.getByText("Read exact chart data", { exact: true }).click();
  await page.getByRole("button", { name: "60D", exact: true }).click();
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "../artifacts/modernization/explorer-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await item.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.screenshot({
    path: "../artifacts/modernization/item-touch-mobile.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  expect(errors).toEqual([]);
});
test("shared deal tooltips and manageable account/admin tables", async ({
  page,
}) => {
  await login(page);
  await expect(
    page.getByRole("heading", { name: "Current listings", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Deal Finder", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "1 opportunity", exact: true }),
  ).toBeVisible();
  await page
    .locator(".deal")
    .getByRole("button", {
      name: "Item details for Synthetic Arcane Crystal",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Synthetic fixture metadata",
  );
  await page.keyboard.press("Escape");
  await page.evaluate(() => scrollTo(0, 0));
  await accessible(page, "deals");
  await page.screenshot({
    path: "../artifacts/modernization/deals-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Market Explorer", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Current listings", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Deal Finder", exact: true }).click();
  await page
    .getByRole("button", { name: "Account & devices", exact: true })
    .click();
  await page.getByLabel("Device name").fill("Modernization browser fixture");
  await page
    .getByRole("button", { name: "Create device token", exact: true })
    .click();
  await page.getByRole("button", { name: "Hide token", exact: true }).click();
  await page
    .getByLabel("Search devices", { exact: true })
    .fill("Modernization");
  await expect(
    page.getByRole("table", { name: "devices", exact: true }),
  ).toContainText("Modernization browser fixture");
  await page.getByRole("button", { name: "Columns", exact: true }).click();
  await expect(page.getByRole("menu")).toBeVisible();
  await page.keyboard.press("Escape");
  await accessible(page, "account");
  await page.screenshot({
    path: "../artifacts/modernization/account-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Administration", exact: true })
    .click();
  await page.getByRole("tab", { name: "Collection", exact: true }).click();
  await expect(
    page.getByLabel("Search collection checks", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../artifacts/modernization/administration-desktop.png",
    fullPage: true,
  });
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(axe.violations).toEqual([]);
});

test("touch item popovers stay readable and dismiss without hover", async ({
  browser,
}) => {
  const context = await browser.newContext({
    baseURL: process.env.BASE_URL || "http://proxy",
    hasTouch: true,
    isMobile: true,
    viewport: { width: 390, height: 844 },
  });
  try {
    const page = await context.newPage();
    await login(page);
    const trigger = page
      .getByRole("region", { name: "Item catalogue", exact: true })
      .getByRole("button", {
        name: "Item details for Synthetic Arcane Crystal",
        exact: true,
      });
    await trigger.tap();
    await expect(page.getByRole("dialog")).toContainText(
      "+10 Fixture Strength",
    );
    await accessible(page, "touch-item");
    await page.screenshot({
      path: "../artifacts/modernization/touch-popover.png",
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Close item details", exact: true })
      .tap();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
  } finally {
    await context.close();
  }
});
