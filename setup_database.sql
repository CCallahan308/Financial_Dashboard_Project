-- Financial Dashboard Database Setup
-- Create schemas and tables for the financial data pipeline

-- Create schemas
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ===================================
-- STAGING TABLES (Raw API Data)
-- ===================================

-- Staging table for raw stock price data from Alpha Vantage
CREATE TABLE IF NOT EXISTS staging.raw_stock_prices (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open_price TEXT,
    high_price TEXT,
    low_price TEXT,
    close_price TEXT,
    volume TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging table for raw news data from NewsAPI
CREATE TABLE IF NOT EXISTS staging.raw_news_articles (
    id SERIAL PRIMARY KEY,
    symbol_searched TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    source_name TEXT,
    published_at TEXT,
    sentiment_score NUMERIC(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging table for raw economic data from FRED API
CREATE TABLE IF NOT EXISTS staging.raw_econ_data (
    id SERIAL PRIMARY KEY,
    series_id TEXT NOT NULL,
    series_date TEXT NOT NULL,
    series_value TEXT,
    series_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===================================
-- ANALYTICS TABLES (Star Schema)
-- ===================================

-- Date dimension table
CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_name TEXT,
    month_name TEXT,
    month_num INTEGER,
    quarter INTEGER,
    year INTEGER,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN DEFAULT FALSE
);

-- Security dimension table
CREATE TABLE IF NOT EXISTS analytics.dim_security (
    security_key SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    company_name TEXT,
    sector TEXT,
    industry TEXT,
    market_cap BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Economic indicator dimension table
CREATE TABLE IF NOT EXISTS analytics.dim_economic_indicator (
    indicator_key SERIAL PRIMARY KEY,
    series_id TEXT NOT NULL UNIQUE,
    indicator_name TEXT,
    description TEXT,
    units TEXT,
    frequency TEXT
);

-- Fact table for stock prices
CREATE TABLE IF NOT EXISTS analytics.fact_prices (
    id SERIAL PRIMARY KEY,
    date_key INTEGER NOT NULL,
    security_key INTEGER NOT NULL,
    open_price NUMERIC(10,2),
    high_price NUMERIC(10,2),
    low_price NUMERIC(10,2),
    close_price NUMERIC(10,2),
    volume BIGINT,
    adjusted_close NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (date_key) REFERENCES analytics.dim_date(date_key),
    FOREIGN KEY (security_key) REFERENCES analytics.dim_security(security_key),
    UNIQUE(date_key, security_key)
);

-- Fact table for news articles
CREATE TABLE IF NOT EXISTS analytics.fact_news (
    article_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date_key INTEGER NOT NULL,
    security_key INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    source_name TEXT,
    sentiment_score NUMERIC(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (date_key) REFERENCES analytics.dim_date(date_key),
    FOREIGN KEY (security_key) REFERENCES analytics.dim_security(security_key)
);

-- Fact table for economic data
CREATE TABLE IF NOT EXISTS analytics.fact_economics (
    id SERIAL PRIMARY KEY,
    date_key INTEGER NOT NULL,
    indicator_key INTEGER NOT NULL,
    value NUMERIC(15,4),
    change_percent NUMERIC(8,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (date_key) REFERENCES analytics.dim_date(date_key),
    FOREIGN KEY (indicator_key) REFERENCES analytics.dim_economic_indicator(indicator_key),
    UNIQUE(date_key, indicator_key)
);

-- ===================================
-- INDEXES FOR PERFORMANCE
-- ===================================

-- Staging table indexes
CREATE INDEX IF NOT EXISTS idx_raw_stock_prices_symbol ON staging.raw_stock_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_raw_stock_prices_date ON staging.raw_stock_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_news_articles_symbol ON staging.raw_news_articles(symbol_searched);
CREATE INDEX IF NOT EXISTS idx_raw_news_articles_published ON staging.raw_news_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_raw_econ_data_series ON staging.raw_econ_data(series_id);
CREATE INDEX IF NOT EXISTS idx_raw_econ_data_date ON staging.raw_econ_data(series_date);

-- Analytics table indexes
CREATE INDEX IF NOT EXISTS idx_fact_prices_date ON analytics.fact_prices(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_prices_security ON analytics.fact_prices(security_key);
CREATE INDEX IF NOT EXISTS idx_fact_news_date ON analytics.fact_news(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_news_security ON analytics.fact_news(security_key);
CREATE INDEX IF NOT EXISTS idx_fact_economics_date ON analytics.fact_economics(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_economics_indicator ON analytics.fact_economics(indicator_key);

-- ===================================
-- GRANTS AND PERMISSIONS
-- ===================================

-- Grant usage on schemas
GRANT USAGE ON SCHEMA staging TO dashboard_user;
GRANT USAGE ON SCHEMA analytics TO dashboard_user;

-- Grant permissions on all tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging TO dashboard_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA analytics TO dashboard_user;

-- Grant permissions on sequences
GRANT USAGE ON ALL SEQUENCES IN SCHEMA staging TO dashboard_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA analytics TO dashboard_user;

-- Add sentiment_score column to staging.raw_news_articles if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'staging'
        AND table_name = 'raw_news_articles'
        AND column_name = 'sentiment_score'
    ) THEN
        ALTER TABLE staging.raw_news_articles ADD COLUMN sentiment_score NUMERIC(3,2);
    END IF;
END $$;
