import { describe, it, expect } from 'vitest';
import  normalizeFleetForBackend from '@/utils/normalizeFleetForBackend.js';

describe('normalizeFleetForBackend', () => {
    it('returns [] when no vehicles provided', () => {
        expect(normalizeFleetForBackend(undefined)).toEqual([]);
        expect(normalizeFleetForBackend(null as any)).toEqual([]);
        expect(normalizeFleetForBackend([])).toEqual([]);
    });

    it('ensures capacity is array and start/end default to 0', () => {
        const out = normalizeFleetForBackend([
            { id: 'v1', capacity: 100 },
            { id: 'v2', capacity: [50, 25], start: 2 },
            { /* no fields */ },
        ]);

        expect(out).toHaveLength(3);

        // v1
        expect(out[0].id).toBe('v1');
        expect(out[0].capacity).toEqual([100]);
        expect(out[0].start).toBe(0);
        expect(out[0].end).toBe(0);

        // v2
        expect(out[1].id).toBe('v2');
        expect(out[1].capacity).toEqual([50, 25]);
        expect(out[1].start).toBe(2);
        expect(out[1].end).toBe(0);

        // v3 (defaults)
        expect(out[2].id).toBe('veh-3');
        expect(Array.isArray(out[2].capacity)).toBe(true);
        expect(out[2].start).toBe(0);
        expect(out[2].end).toBe(0);
    });
});
