-- =====================================================================
-- ReviewPulse: business questions answered in SQL
-- Portable SQL (SQLite 3.25+, PostgreSQL, MySQL 8+). Run them all with:
--     python scripts/run_sql.py
-- Each query is separated by a line starting with "-- Q".
-- =====================================================================

-- Q1. How is customer sentiment moving week over week? (CTE + LAG window function)
WITH weekly AS (
    SELECT week_start,
           COUNT(*)                                                         AS reviews,
           ROUND(AVG(rating), 2)                                            AS avg_rating,
           ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_negative
    FROM reviews
    GROUP BY week_start
)
SELECT week_start, reviews, avg_rating, pct_negative,
       ROUND(avg_rating - LAG(avg_rating) OVER (ORDER BY week_start), 2) AS rating_change_wow
FROM weekly
ORDER BY week_start DESC
LIMIT 8;

-- Q2. Smooth out weekly noise: 4-week rolling average rating (window frame)
WITH weekly AS (
    SELECT week_start, AVG(rating) AS avg_rating FROM reviews GROUP BY week_start
)
SELECT week_start,
       ROUND(avg_rating, 2) AS avg_rating,
       ROUND(AVG(avg_rating) OVER (ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2) AS rolling_4wk
FROM weekly
ORDER BY week_start DESC
LIMIT 8;

-- Q3. Rank cities by customer satisfaction (RANK window function)
SELECT city,
       COUNT(*) AS reviews,
       ROUND(100.0 * AVG(CASE WHEN rating >= 4 THEN 1.0 ELSE 0 END), 1) AS csat_pct,
       RANK() OVER (ORDER BY AVG(CASE WHEN rating >= 4 THEN 1.0 ELSE 0 END) DESC) AS csat_rank
FROM reviews
GROUP BY city
HAVING COUNT(*) >= 30
ORDER BY csat_rank;

-- Q4. What are the top 2 complaints in each city? (JOIN + ROW_NUMBER per partition)
WITH city_topic AS (
    SELECT r.city, t.topic, COUNT(*) AS negative_mentions
    FROM reviews r
    JOIN review_topics t ON t.review_id = r.id
    WHERE r.sentiment_label = 'negative' AND t.topic <> 'Other'
    GROUP BY r.city, t.topic
), ranked AS (
    SELECT city, topic, negative_mentions,
           ROW_NUMBER() OVER (PARTITION BY city ORDER BY negative_mentions DESC) AS rn
    FROM city_topic
)
SELECT city, topic, negative_mentions, rn AS complaint_rank
FROM ranked
WHERE rn <= 2
ORDER BY city, rn;

-- Q5. Share of each topic in all negative feedback (window SUM over the whole result)
SELECT t.topic,
       COUNT(*) AS negative_mentions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
FROM review_topics t
JOIN reviews r ON r.id = t.review_id
WHERE r.sentiment_label = 'negative'
GROUP BY t.topic
ORDER BY negative_mentions DESC;

-- Q6. Hidden dissatisfaction: high stars but negative words, by platform
SELECT platform,
       COUNT(*) AS reviews,
       SUM(CASE WHEN rating >= 4 AND sentiment_label = 'negative' THEN 1 ELSE 0 END) AS happy_stars_unhappy_words,
       ROUND(100.0 * SUM(CASE WHEN mismatch THEN 1 ELSE 0 END) / COUNT(*), 1) AS mismatch_pct
FROM reviews
GROUP BY platform
ORDER BY mismatch_pct DESC;

-- Q7. Did the iOS problem start at a specific week? (conditional aggregation / pivot)
SELECT week_start,
       SUM(CASE WHEN platform = 'iOS'     AND sentiment_label = 'negative' THEN 1 ELSE 0 END) AS ios_negative,
       SUM(CASE WHEN platform = 'Android' AND sentiment_label = 'negative' THEN 1 ELSE 0 END) AS android_negative,
       SUM(CASE WHEN platform = 'Web'     AND sentiment_label = 'negative' THEN 1 ELSE 0 END) AS web_negative
FROM reviews r
WHERE EXISTS (SELECT 1 FROM review_topics t WHERE t.review_id = r.id AND t.topic = 'App Experience')
GROUP BY week_start
ORDER BY week_start DESC
LIMIT 8;
