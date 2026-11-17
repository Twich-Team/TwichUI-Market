import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', workers:1, timeout:60000,
  use:{hasTouch:true,isMobile:true,baseURL:process.env.BASE_URL || 'http://127.0.0.1:5173',
    launchOptions:process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : undefined,
    screenshot:'only-on-failure'},
  outputDir:'../artifacts/mobile-tests',reporter:'list',
});
