-- Heartbeat for scheduled work.
--
-- The failure this exists to prevent is silence. A nightly job that dies, or
-- that runs happily against a source which published nothing, looks exactly
-- like a nightly job that had nothing to do -- and the daily scan then reports
-- on stale data without anyone noticing. So every run writes a row, and
-- "the market traded and no new data arrived" is its own status rather than a
-- quiet success.
CREATE TABLE IF NOT EXISTS job_run (
    run_id        bigserial PRIMARY KEY,
    job           text NOT NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'ok', 'no_new_data',
                                    'stale_source', 'failed')),
    source_date   date,          -- the publication date the source offered
    trade_date    date,          -- the session actually loaded, if any
    rows_added    integer NOT NULL DEFAULT 0,
    build_id      bigint REFERENCES adjustment_build(build_id),
    restatement   boolean NOT NULL DEFAULT false,
    message       text
);

CREATE INDEX IF NOT EXISTS job_run_job_started_idx ON job_run (job, started_at DESC);

COMMENT ON COLUMN job_run.status IS
    'ok = new session loaded; no_new_data = ran before the source published; '
    'stale_source = a session passed and the source still has nothing (needs '
    'attention); failed = the run raised; running = never finished, which is '
    'itself a signal';
