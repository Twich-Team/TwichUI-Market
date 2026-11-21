import {defineConfig} from '@playwright/test';
import base from './playwright.config';
export default defineConfig({...base,testMatch:'backup-management.spec.ts',use:{...base.use,browserName:'webkit'},outputDir:'../artifacts/backup-management-webkit'});
