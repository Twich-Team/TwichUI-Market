// Run with Playwright 1.56.1 and its matching Chromium image.
const { chromium } = require('/tmp/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, args:['--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  for (const [route, heading] of [['explorer','Market Explorer'],['deals','Deal Finder'],['admin','Administration']]) {
    await page.goto(`http://proxy/design/#${route}`);
    await page.getByRole('heading', {name:heading,exact:true}).waitFor();
    assert(await page.getByText('DESIGN REVIEW · VERSION 1').isVisible());
    await page.screenshot({path:`/work/artifacts/design/${route}-desktop.png`,fullPage:true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),`${route}: desktop horizontal overflow`);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:`/work/artifacts/design/${route}-mobile.png`,fullPage:true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),`${route}: mobile horizontal overflow`);
    await page.setViewportSize({width:1440,height:1100});
  }
  await page.getByRole('button',{name:'+ Invite a friend'}).click();
  assert(await page.getByRole('dialog').isVisible());
  await page.getByRole('button',{name:'Understood'}).click();
  await page.getByRole('link',{name:'◇ Deal Finder'}).click();
  await page.getByRole('button',{name:'Apply filters'}).click();
  assert(await page.getByRole('dialog').isVisible());
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('Verified 3 desktop/mobile mockups, navigation and review dialogs; no page errors.');
})().catch(error => {console.error(error);process.exit(1)});
