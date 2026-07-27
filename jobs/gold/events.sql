-- gold/events.sql
-- Event counts by type for today (UTC).
-- Reads from silver (clean, deduplicated, typed timestamps).
-- Overwrites gold/events/ each run (runner deletes target before INSERT).

INSERT INTO gold_events
SELECT
    event_type,
    COUNT(*) AS count
FROM silver
WHERE
    year  = EXTRACT(year  FROM now())
    AND month = EXTRACT(month FROM now())
    AND day   = EXTRACT(day   FROM now())
GROUP BY event_type
ORDER BY count DESC
