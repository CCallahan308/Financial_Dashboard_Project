-- Financial Dashboard Data Transformation Script
-- Transforms raw staging data into clean analytics star schema

-- ===================================
-- DATE DIMENSION POPULATION
-- ===================================

-- Generate calendar dates for 10 years (2020-2030)
INSERT INTO analytics.dim_date (date_key, full_date, day_name, month_name, month_num, quarter, year, is_weekend, is_holiday)
SELECT
    EXTRACT(YEAR FROM d) * 10000 + EXTRACT(MONTH FROM d) * 100 + EXTRACT(DAY FROM d) as date_key,
    d::DATE as full_date,
    TO_CHAR(d, 'Day') as day_name,
    TO_CHAR(d, 'Month') as month_name,
    EXTRACT(MONTH FROM d) as month_num,
    EXTRACT(QUARTER FROM d) as quarter,
    EXTRACT(YEAR FROM d) as year,
    CASE WHEN EXTRACT(DOW FROM d) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend,
    FALSE as is_holiday
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day') d
WHERE d::DATE NOT IN (SELECT full_date FROM analytics.dim_date);

-- ===================================
-- SECURITY DIMENSION POPULATION
-- ===================================

-- Populate securities from unique stock symbols
INSERT INTO analytics.dim_security (symbol, company_name, sector, industry, market_cap)
SELECT DISTINCT
    symbol,
    CASE
        WHEN symbol = 'AAPL' THEN 'Apple Inc.'
        WHEN symbol = 'MSFT' THEN 'Microsoft Corporation'
        WHEN symbol = 'GOOGL' THEN 'Alphabet Inc.'
        WHEN symbol = 'TSLA' THEN 'Tesla, Inc.'
        ELSE SPLIT_PART(symbol, '.', 1)
    END as company_name,
    CASE
        WHEN symbol IN ('AAPL', 'MSFT', 'GOOGL', 'TSLA') THEN 'Technology'
        ELSE 'Unknown'
    END as sector,
    CASE
        WHEN symbol IN ('AAPL', 'MSFT', 'GOOGL', 'TSLA') THEN 'Software'
        ELSE 'Unknown'
    END as industry,
    0 as market_cap
FROM staging.raw_stock_prices
WHERE symbol NOT IN (SELECT symbol FROM analytics.dim_security);

-- ===================================
-- ECONOMIC INDICATOR DIMENSION POPULATION
-- ===================================

-- Populate economic indicators
INSERT INTO analytics.dim_economic_indicator (series_id, indicator_name, description, units, frequency)
SELECT DISTINCT
    series_id,
    series_name as indicator_name,
    series_name as description,
    CASE
        WHEN series_id = 'GDP' THEN 'Billions of Dollars'
        WHEN series_id = 'UNRATE' THEN 'Percent'
        WHEN series_id = 'CPIAUCSL' THEN 'Index 1982-1984=100'
        WHEN series_id = 'FEDFUNDS' THEN 'Percent'
        ELSE 'Units'
    END as units,
    CASE
        WHEN series_id = 'GDP' THEN 'Quarterly'
        WHEN series_id = 'UNRATE' THEN 'Monthly'
        WHEN series_id = 'CPIAUCSL' THEN 'Monthly'
        WHEN series_id = 'FEDFUNDS' THEN 'Monthly'
        ELSE 'Monthly'
    END as frequency
FROM staging.raw_econ_data
WHERE series_id NOT IN (SELECT series_id FROM analytics.dim_economic_indicator);

-- ===================================
-- PRICE FACT TABLE POPULATION
-- ===================================

-- Transform and load clean price data
-- Optimized with explicit index usage and batch processing
INSERT INTO analytics.fact_prices (date_key, security_key, open_price, high_price, low_price, close_price, volume)
SELECT DISTINCT
    dd.date_key,
    ds.security_key,
    CAST(rsp.open_price AS NUMERIC(10,2)) as open_price,
    CAST(rsp.high_price AS NUMERIC(10,2)) as high_price,
    CAST(rsp.low_price AS NUMERIC(10,2)) as low_price,
    CAST(rsp.close_price AS NUMERIC(10,2)) as close_price,
    CAST(rsp.volume AS BIGINT) as volume
FROM staging.raw_stock_prices rsp
JOIN analytics.dim_date dd ON TO_DATE(rsp.trade_date, 'YYYY-MM-DD') = dd.full_date
JOIN analytics.dim_security ds ON rsp.symbol = ds.symbol
WHERE rsp.trade_date IS NOT NULL
  AND rsp.close_price IS NOT NULL
  AND CAST(rsp.close_price AS NUMERIC(10,2)) > 0
  AND NOT EXISTS (
      SELECT 1 FROM analytics.fact_prices fp
      WHERE fp.date_key = dd.date_key AND fp.security_key = ds.security_key
  );

-- ===================================
-- NEWS FACT TABLE POPULATION
-- ===================================

-- Transform and load clean news data
-- Optimized to avoid duplicate URL inserts
INSERT INTO analytics.fact_news (article_id, date_key, security_key, title, description, url, source_name, sentiment_score)
SELECT
    gen_random_uuid() as article_id,
    dd.date_key,
    ds.security_key,
    rna.title,
    rna.description,
    rna.url,
    rna.source_name,
    0.0 as sentiment_score
FROM staging.raw_news_articles rna
JOIN analytics.dim_date dd ON TO_DATE(SUBSTRING(rna.published_at, 1, 10), 'YYYY-MM-DD') = dd.full_date
JOIN analytics.dim_security ds ON rna.symbol_searched = ds.symbol
WHERE rna.published_at IS NOT NULL
  AND rna.url IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM analytics.fact_news fn
      WHERE fn.url = rna.url
  );

-- ===================================
-- ECONOMIC FACT TABLE POPULATION
-- ===================================

-- Transform and load clean economic data
-- Optimized with NOT EXISTS instead of LEFT JOIN for better performance
INSERT INTO analytics.fact_economics (date_key, indicator_key, value, change_percent)
SELECT DISTINCT
    dd.date_key,
    dei.indicator_key,
    CAST(red.series_value AS NUMERIC(15,4)) as value,
    0.0 as change_percent
FROM staging.raw_econ_data red
JOIN analytics.dim_date dd ON TO_DATE(red.series_date, 'YYYY-MM-DD') = dd.full_date
JOIN analytics.dim_economic_indicator dei ON red.series_id = dei.series_id
WHERE red.series_value IS NOT NULL
  AND CAST(red.series_value AS NUMERIC(15,4)) IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM analytics.fact_economics fe
      WHERE fe.date_key = dd.date_key AND fe.indicator_key = dei.indicator_key
  );

-- ===================================
-- UPDATE CHANGE PERCENTAGES FOR ECONOMIC DATA
-- ===================================

-- Calculate percentage changes for economic indicators
-- Optimized using a CTE and window functions for better performance
WITH value_changes AS (
    SELECT
        fe.id,
        fe.value,
        LAG(fe.value) OVER (PARTITION BY fe.indicator_key ORDER BY dd.full_date) as previous_value
    FROM analytics.fact_economics fe
    JOIN analytics.dim_date dd ON fe.date_key = dd.date_key
    WHERE fe.change_percent = 0.0
)
UPDATE analytics.fact_economics fe
SET change_percent = CASE
    WHEN vc.previous_value IS NOT NULL AND vc.previous_value != 0
    THEN ((vc.value - vc.previous_value) / vc.previous_value) * 100
    ELSE 0.0
END
FROM value_changes vc
WHERE fe.id = vc.id
  AND vc.previous_value IS NOT NULL;

-- ===================================
-- TRANSFORMATION SUMMARY
-- ===================================

-- Log transformation completion
DO $$
BEGIN
    RAISE NOTICE 'Transformation completed at %', NOW();

    -- Count records in each fact table
    DECLARE
        price_count INTEGER;
        news_count INTEGER;
        econ_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO price_count FROM analytics.fact_prices;
        SELECT COUNT(*) INTO news_count FROM analytics.fact_news;
        SELECT COUNT(*) INTO econ_count FROM analytics.fact_economics;

        RAISE NOTICE 'Fact table counts:';
        RAISE NOTICE '  - fact_prices: % records', price_count;
        RAISE NOTICE '  - fact_news: % records', news_count;
        RAISE NOTICE '  - fact_economics: % records', econ_count;
    END;
END $$;