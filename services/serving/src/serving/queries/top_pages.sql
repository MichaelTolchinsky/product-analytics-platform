SELECT page, views, rn
FROM gold_top_pages
WHERE rn <= $limit
ORDER BY rn
