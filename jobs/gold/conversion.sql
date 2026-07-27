-- gold/conversion.sql
-- Session-scoped signup → purchase conversion rate for today (UTC).
-- DuckDB-compatible: CTEs expressed as subqueries (no INSERT INTO ... WITH).

INSERT INTO gold_conversion
SELECT
    COUNT(DISTINCT c.session_id)                              AS converted_sessions,
    COUNT(DISTINCT s.session_id)                              AS total_signup_sessions,
    ROUND(
        100.0 * COUNT(DISTINCT c.session_id)
              / NULLIF(COUNT(DISTINCT s.session_id), 0),
        2
    )                                                         AS conversion_rate_pct
FROM (
    SELECT session_id, MIN(timestamp) AS signed_up_at
    FROM silver
    WHERE event_type = 'signup'
      AND year  = EXTRACT(year  FROM now())
      AND month = EXTRACT(month FROM now())
      AND day   = EXTRACT(day   FROM now())
    GROUP BY session_id
) s
LEFT JOIN (
    SELECT s2.session_id
    FROM (
        SELECT session_id, MIN(timestamp) AS signed_up_at
        FROM silver
        WHERE event_type = 'signup'
          AND year  = EXTRACT(year  FROM now())
          AND month = EXTRACT(month FROM now())
          AND day   = EXTRACT(day   FROM now())
        GROUP BY session_id
    ) s2
    JOIN (
        SELECT session_id, MIN(timestamp) AS purchased_at
        FROM silver
        WHERE event_type = 'purchase'
          AND year  = EXTRACT(year  FROM now())
          AND month = EXTRACT(month FROM now())
          AND day   = EXTRACT(day   FROM now())
        GROUP BY session_id
    ) p ON s2.session_id = p.session_id
       AND p.purchased_at > s2.signed_up_at
) c ON s.session_id = c.session_id
