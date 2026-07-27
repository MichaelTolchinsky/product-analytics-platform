-- gold/dau.sql
-- Compute Daily Active Users (DAU): distinct users for today (UTC).
-- Reads from silver (clean, deduplicated, typed timestamps).
-- Overwrites gold/dau/ each run (runner deletes target before INSERT).

INSERT INTO gold_dau
SELECT
    CAST(date_trunc('day', timestamp) AS DATE) AS date,
    COUNT(DISTINCT user_id)                    AS dau
FROM silver
WHERE
    year  = EXTRACT(year  FROM now())
    AND month = EXTRACT(month FROM now())
    AND day   = EXTRACT(day   FROM now())
GROUP BY CAST(date_trunc('day', timestamp) AS DATE)
