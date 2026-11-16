import { test, expect } from '@playwright/test';

test('ForeverDB ownership proof is public exact plain text, without SPA fallback', async ({ request }) => {
  const response = await request.get('/.well-known/foreverdb.txt', { maxRedirects: 0 });
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toMatch(/^text\/plain(?:;|$)/);
  expect(await response.body()).toEqual(Buffer.from('dev-0255', 'utf8'));
  expect(response.headers()['location']).toBeUndefined();
  expect(response.headers()['set-cookie']).toBeUndefined();
});
