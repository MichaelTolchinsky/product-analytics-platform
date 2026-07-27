SELECT query, count, rn
FROM gold_searches
WHERE rn <= $limit
ORDER BY rn
