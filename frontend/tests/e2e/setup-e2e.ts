import { server } from '../unit/mocks/server';
import { test as base } from '@playwright/test';

server.listen({ onUnhandledRequest: 'bypass' });
export const test = base;
export const expect = base.expect;

export function teardown() { server.close(); }