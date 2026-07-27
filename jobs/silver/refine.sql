-- silver/refine.sql
-- bronze -> silver: filter, validate, dedupe, cast types.
-- DuckDB-compatible syntax (Floci local) and Athena/Presto (production).

INSERT INTO silver
SELECT
    event_id,
    event_type,
    timestamp,
    user_id,
    session_id,
    page,
    metadata,
    year,
    month,
    day,
    hour
FROM (
    SELECT
        event_id,
        event_type,
        TRY_CAST(timestamp AS TIMESTAMPTZ) AS timestamp,
        user_id,
        session_id,
        page,
        metadata,
        year,
        month,
        day,
        hour,
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY timestamp ASC
        ) AS rn
    FROM (
        SELECT *
        FROM bronze
        WHERE
            make_timestamp(
                year::BIGINT, month::BIGINT, day::BIGINT, hour::BIGINT, 0, 0
            ) >= date_trunc('hour', now()) - INTERVAL 3 HOURS
            AND event_id   IS NOT NULL AND event_id   != ''
            AND event_type IS NOT NULL AND event_type IN (
                'page_view', 'button_click', 'search', 'signup', 'purchase'
            )
            AND timestamp  IS NOT NULL AND timestamp  != ''
            AND user_id    IS NOT NULL AND user_id    != ''
            AND session_id IS NOT NULL AND session_id != ''
            AND page       IS NOT NULL AND page       != ''
    )
) WHERE rn = 1
