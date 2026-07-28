-- analytics/hourly_events.sql
-- Event count per hour for today (UTC), scanning today's silver partitions.
-- Athena path: partition-pruned scan, flexible aggregation.

SELECT
    EXTRACT(hour FROM timestamp) AS hour,
    COUNT(*)                     AS count
FROM silver
WHERE
    year  = EXTRACT(year  FROM current_date)
    AND month = EXTRACT(month FROM current_date)
    AND day   = EXTRACT(day   FROM current_date)
GROUP BY EXTRACT(hour FROM timestamp)
ORDER BY hour ASC
