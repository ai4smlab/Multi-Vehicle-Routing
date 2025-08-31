import { Page } from '@playwright/test';

// Wait until the page has mounted and exposed the stores
export async function waitForStores(page: Page) {
  await page.waitForFunction(() =>
    typeof window !== 'undefined' &&
    !!(window as any).useUiStore &&
    !!(window as any).useRouteStore &&
    !!(window as any).useWaypointStore &&
    !!(window as any).useMapStore
  );
}

// Convenient wrapper to run code in the browser against stores
export async function withStores<T>(
  page: Page,
  fn: (stores: {
    useUiStore: Window['useUiStore'],
    useRouteStore: Window['useRouteStore'],
    useWaypointStore: Window['useWaypointStore'],
    useMapStore: Window['useMapStore'],
  }) => T | Promise<T>
): Promise<T> {
  return page.evaluate(fn as any, null);
}