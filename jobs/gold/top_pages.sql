-- gold/top_pages.sql
-- Most visited pages today, ranked by page_view count descending.
-- ROW_NUMBER produces exactly N rows with no gaps or ties.

INSERT INTO gold_top_pages
SELECT page, views, ROW_NUMBER() OVER (ORDER BY views DESC) AS rn
FROM (
    SELECT page, COUNT(*) AS views
    FROM silver
    WHERE
        event_type = 'page_view'
        AND year  = EXTRACT(year  FROM now())
        AND month = EXTRACT(month FROM now())
        AND day   = EXTRACT(day   FROM now())
    GROUP BY page
)
ORDER BY rn
