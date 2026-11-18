import {defineConfig} from '@playwright/test';
import base from './playwright.webkit.config';
export default defineConfig({...base,testMatch:'unified-coverage.spec.ts',outputDir:'../artifacts/commodity-webkit-tests'});
