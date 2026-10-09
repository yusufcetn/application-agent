import test from 'node:test'
import assert from 'node:assert/strict'
import { isFresh, isFromLatestRun } from './freshness.ts'

const run = { started_at: '2026-10-02T09:22:50' }

test('only jobs saved since the latest run started are fresh', () => {
  assert.equal(isFromLatestRun({ found_at: '2026-10-02T09:30:00' }, run), true)
  assert.equal(isFromLatestRun({ found_at: '2026-09-27T16:55:00' }, run), false)
  assert.equal(isFromLatestRun({ found_at: '2026-10-02T09:30:00' }, undefined), false)
})

test('a job already opened or acted on loses the badge', () => {
  assert.equal(isFresh({ found_at: '2026-10-02T09:30:00', status: 'new', seen_at: null }, run), true)
  assert.equal(isFresh({ found_at: '2026-10-02T09:30:00', status: 'new', seen_at: '2026-10-02T10:00:00' }, run), false)
  assert.equal(isFresh({ found_at: '2026-10-02T09:30:00', status: 'applied', seen_at: null }, run), false)
})
