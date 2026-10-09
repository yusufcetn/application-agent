import type { Job, SearchRun } from './api/types'

// Jobs saved since the latest search run started: what that run found, plus any added by hand since.
export const isFromLatestRun = (job: Pick<Job, 'found_at'>, run: Pick<SearchRun, 'started_at'> | null | undefined): boolean =>
  Boolean(run) && Date.parse(job.found_at) >= Date.parse(run!.started_at)

// The "Yeni" badge: from the latest run, not opened and not acted on yet.
export const isFresh = (job: Pick<Job, 'found_at' | 'status' | 'seen_at'>, run: Pick<SearchRun, 'started_at'> | null | undefined): boolean =>
  job.status === 'new' && !job.seen_at && isFromLatestRun(job, run)
