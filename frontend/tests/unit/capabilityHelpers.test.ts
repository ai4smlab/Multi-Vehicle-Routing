// tests/unit/capabilityHelpers.test.ts
import { describe, it, expect } from 'vitest';
import { evaluateRequirements, getVrpSpec, getSolverSpec } from '@/utils/capabilityHelpers';

describe('capability helpers', () => {
    const caps = {
        solvers: [{ name: 'ortools' }, { name: 'vroom' }],
        adapters: [{ name: 'haversine' }, { name: 'osm_graph' }],
        vrp_specs: {
            ortools: {
                vrp_types: {
                    TSP: { required: ['matrix'], optional: [] },
                    CVRP: { required: ['matrix', 'demands'], optional: [] },
                    VRPTW: { required: ['matrix', 'node_time_windows', 'node_service_times'], optional: [] }
                }
            }
        }
    };

    it('getSolverSpec returns the solver block', () => {
        const spec = getSolverSpec(caps, 'ortools');
        expect(spec?.vrp_types?.TSP).toBeTruthy();
        expect(spec?.vrp_types?.CVRP?.required).toContain('demands');
    });

    it('getVrpSpec returns per-type spec', () => {
        const tsp = getVrpSpec(caps, 'ortools', 'TSP');
        expect(tsp?.required).toEqual(['matrix']);
    });

    it('evaluateRequirements marks tokens present/absent', () => {
        const req = ['matrix', 'demands', 'node_time_windows'];
        const ctx = {
            matrix: { distances: [[0, 1], [1, 0]] },
            demands: [0, 1],
            node_time_windows: null
        };
        const checks = evaluateRequirements(req, ctx);

        const by = Object.fromEntries(checks.map(c => [c.token, c.ok]));
        expect(by.matrix).toBe(true);
        expect(by.demands).toBe(true);
        expect(by.node_time_windows).toBe(false);
    });
});
