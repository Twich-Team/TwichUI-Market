// Executes against the installed Windows WebView2 and real Tauri IPC, never mocked.
const { chromium, expect } = require('@playwright/test');
const fs = require('node:fs');
(async () => {
  const endpoint = `http://127.0.0.1:${process.env.MARKET_TEST_CDP_PORT}`;
  await expect.poll(async () => {
    try { return (await fetch(`${endpoint}/json/version`)).ok; } catch { return false; }
  }, {timeout:30000}).toBe(true);
  const browser = await chromium.connectOverCDP(endpoint);
  try {
    const page = browser.contexts()[0].pages()[0];
    await expect(page.locator('#server')).toBeVisible();
    await page.locator('#server').fill(process.env.MARKET_TEST_SERVER);
    await page.locator('#token').fill(process.env.MARKET_TEST_TOKEN);
    await page.getByRole('button', { name: 'Connect securely', exact: true }).click();
    await expect(page.locator('#message')).toContainText('Connected.');
    await expect(page.locator('#token')).toHaveValue('');
    await page.locator('#market').fill('1');
    await page.locator('#sync').click();
    await expect(page.locator('#message')).toContainText('Synchronization complete.',{timeout:30000});
    await expect(page.locator('#count')).toContainText('2 item variants');
    await page.locator('#export').click();
    await expect(page.locator('#message')).toContainText('Data-only JSON exported:');
    const path = (await page.locator('#message').innerText()).replace('Data-only JSON exported: ', '');
    const data = JSON.parse(fs.readFileSync(path,'utf8'));
    fs.writeFileSync(process.env.MARKET_TEST_EXPORT_RECORD, JSON.stringify(data));
    expect(data.format).toBe('twichui-market-addon-data');
    expect(data.synthetic).toBe(true);
    expect(data.items).toHaveLength(2);
    expect(data.items[0].value.recent_price).toBe('100');
    await page.locator('#disconnect').click();
    await expect(page.locator('#message')).toContainText('Local credential removed.');
    console.log('Installed WebView2: native vault connection, real API sync, safe JSON export and disconnect verified.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
