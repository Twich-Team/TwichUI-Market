import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', testMatch:'mobile-experience.spec.ts', workers:1, timeout:90000,
  use:{browserName:'webkit',baseURL:process.env.BASE_URL || 'http://proxy',hasTouch:true,isMobile:true,
    trace:'retain-on-failure',screenshot:'only-on-failure'},
  outputDir:'../artifacts/mobile-webkit-tests',reporter:'list',
});
