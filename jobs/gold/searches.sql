-- gold/searches.sql
-- Top search terms today, ranked by frequency descending.
-- metadata JSON string column — json_extract_string pulls out the query key.

INSERT INTO gold_searches
SELECT query, count, ROW_NUMBER() OVER (ORDER BY count DESC) AS rn
FROM (
    SELECT
        json_extract_string(metadata, '$.query') AS query,
        COUNT(*) AS count
    FROM silver
    WHERE
        event_type = 'search'
        AND year  = EXTRACT(year  FROM now())
        AND month = EXTRACT(month FROM now())
        AND day   = EXTRACT(day   FROM now())
    GROUP BY json_extract_string(metadata, '$.query')
    HAVING json_extract_string(metadata, '$.query') IS NOT NULL
       AND json_extract_string(metadata, '$.query') != ''
)
ORDER BY rn
