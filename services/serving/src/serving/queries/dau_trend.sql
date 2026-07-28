-- analytics/dau_trend.sql
-- DAU per day for the last $days days, scanning silver directly.
-- Athena path: flexible date range, not pre-computed.

SELECT
    CAST(date_trunc('day', timestamp) AS DATE) AS date,
    COUNT(DISTINCT user_id)                    AS dau
FROM silver
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '$days' DAY
GROUP BY CAST(date_trunc('day', timestamp) AS DATE)
ORDER BY date ASC
