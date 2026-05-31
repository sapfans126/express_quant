--==========有code 但没有basic info 的股票
SELECT cl.code
FROM codes_list cl
LEFT JOIN basic_info bi ON cl.code = bi.code
WHERE bi.code IS NULL;