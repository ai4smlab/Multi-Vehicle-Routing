// tests/unit/setup-dom.ts
import '@testing-library/jest-dom/vitest'; // registers matchers on Vitest's expect
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Clean up the DOM after each test
afterEach(() => cleanup());
