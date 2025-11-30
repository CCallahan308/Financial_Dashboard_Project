#!/usr/bin/env python3
"""
Financial Dashboard Data Pipeline
Extracts data from multiple APIs, loads into staging, transforms to analytics schema
"""

import os
import requests
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
FRED_API_KEY = os.getenv('FRED_API_KEY')
BASE_STOCK_SYMBOLS = os.getenv('BASE_STOCK_SYMBOLS', 'AAPL,MSFT,GOOGL,TSLA').split(',')
ECONOMIC_SERIES = os.getenv('ECONOMIC_SERIES', 'GDP,UNRATE,CPIAUCSL,FEDFUNDS').split(',')

# Validate required environment variables
required_vars = [DATABASE_URL, ALPHA_VANTAGE_API_KEY, NEWSAPI_KEY, FRED_API_KEY]
for var in required_vars:
    if not var:
        raise ValueError("Missing required environment variable. Please check your .env file.")

# Global database engine
engine = None


def get_db_engine():
    """Get or create database engine with connection pooling"""
    global engine
    if engine is None:
        engine = create_engine(
            DATABASE_URL,
            pool_size=5,            # Maintain 5 connections in the pool
            max_overflow=10,        # Allow up to 10 additional connections
            pool_pre_ping=True,     # Verify connections before using them
            pool_recycle=3600       # Recycle connections after 1 hour
        )
    return engine


def extract_stock_data(symbols: List[str]) -> pd.DataFrame:
    """
    Extract stock price data from Alpha Vantage API

    Args:
        symbols: List of stock symbols to fetch data for

    Returns:
        pandas DataFrame with columns matching staging.raw_stock_prices
    """
    logger.info(f"Extracting stock data for symbols: {symbols}")

    all_data = []
    base_url = "https://www.alphavantage.co/query"

    for symbol in symbols:
        try:
            logger.info(f"Fetching data for symbol: {symbol}")

            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'outputsize': 'compact',
                'apikey': ALPHA_VANTAGE_API_KEY
            }

            response = requests.get(base_url, params=params)
            response.raise_for_status()

            data = response.json()

            # Handle API errors
            if 'Error Message' in data:
                logger.error(f"Alpha Vantage API error for {symbol}: {data['Error Message']}")
                continue

            if 'Note' in data:
                logger.warning(f"Alpha Vantage API rate limit reached for {symbol}")
                break

            if 'Time Series (Daily)' not in data:
                logger.warning(f"No time series data found for {symbol}")
                continue

            time_series = data['Time Series (Daily)']

            for date_str, price_data in time_series.items():
                all_data.append({
                    'symbol': symbol,
                    'trade_date': date_str,
                    'open_price': price_data['1. open'],
                    'high_price': price_data['2. high'],
                    'low_price': price_data['3. low'],
                    'close_price': price_data['4. close'],
                    'volume': price_data['5. volume']
                })

            # Rate limiting: Alpha Vantage free tier allows 5 calls per minute
            logger.info(f"Rate limiting: waiting 12 seconds before next API call")
            time.sleep(12)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for symbol {symbol}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing symbol {symbol}: {e}")
            continue

    df = pd.DataFrame(all_data)
    logger.info(f"Extracted {len(df)} stock price records")
    return df


def extract_news_data(symbols: List[str]) -> pd.DataFrame:
    """
    Extract news articles from NewsAPI

    Args:
        symbols: List of stock symbols to search for in news

    Returns:
        pandas DataFrame with columns matching staging.raw_news_articles
    """
    logger.info(f"Extracting news data for symbols: {symbols}")

    all_data = []
    base_url = "https://newsapi.org/v2/everything"

    # Calculate date range (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    for symbol in symbols:
        try:
            logger.info(f"Fetching news for symbol: {symbol}")

            params = {
                'q': symbol,
                'from': start_date.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 50,
                'apiKey': NEWSAPI_KEY
            }

            response = requests.get(base_url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get('status') != 'ok':
                logger.error(f"NewsAPI error for {symbol}: {data.get('message', 'Unknown error')}")
                continue

            articles = data.get('articles', [])

            for article in articles:
                all_data.append({
                    'symbol_searched': symbol,
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'source_name': article.get('source', {}).get('name', ''),
                    'published_at': article.get('publishedAt', '')
                })

            logger.info(f"Found {len(articles)} articles for {symbol}")

            # Small delay between requests
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for symbol {symbol}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing news for symbol {symbol}: {e}")
            continue

    df = pd.DataFrame(all_data)
    logger.info(f"Extracted {len(df)} news articles")
    return df


def extract_econ_data(series_ids: List[str]) -> pd.DataFrame:
    """
    Extract economic data from FRED API

    Args:
        series_ids: List of FRED series IDs to fetch data for

    Returns:
        pandas DataFrame with columns matching staging.raw_econ_data
    """
    logger.info(f"Extracting economic data for series: {series_ids}")

    all_data = []
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    # Calculate date range (last 2 years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)

    for series_id in series_ids:
        try:
            logger.info(f"Fetching economic data for series: {series_id}")

            # First get series info
            series_info_url = "https://api.stlouisfed.org/fred/series"
            series_params = {
                'series_id': series_id,
                'api_key': FRED_API_KEY,
                'file_type': 'json'
            }

            series_response = requests.get(series_info_url, params=series_params)
            series_response.raise_for_status()
            series_info = series_response.json()

            series_name = series_info.get('seriess', [{}])[0].get('title', series_id)

            # Get observations
            obs_params = {
                'series_id': series_id,
                'api_key': FRED_API_KEY,
                'file_type': 'json',
                'observation_start': start_date.strftime('%Y-%m-%d'),
                'observation_end': end_date.strftime('%Y-%m-%d')
            }

            response = requests.get(base_url, params=obs_params)
            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                logger.error(f"FRED API error for {series_id}: {data['error']}")
                continue

            observations = data.get('observations', [])

            for obs in observations:
                if obs.get('value') != '.' and obs.get('value') is not None:
                    all_data.append({
                        'series_id': series_id,
                        'series_date': obs.get('date', ''),
                        'series_value': obs.get('value', ''),
                        'series_name': series_name
                    })

            logger.info(f"Found {len(observations)} observations for {series_id}")

            # Small delay between requests
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for series {series_id}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing series {series_id}: {e}")
            continue

    df = pd.DataFrame(all_data)
    logger.info(f"Extracted {len(df)} economic data points")
    return df


def load_to_staging(dataframe: pd.DataFrame, table_name: str) -> int:
    """
    Generic function to load pandas DataFrame into staging tables
    Optimized with bulk inserts using multi-row INSERT

    Args:
        dataframe: pandas DataFrame with data to load
        table_name: target table name (without schema prefix)

    Returns:
        Number of rows loaded
    """
    if dataframe.empty:
        logger.warning(f"Empty DataFrame provided for table {table_name}")
        return 0

    try:
        engine = get_db_engine()
        full_table_name = f"staging.{table_name}"

        # Load data to staging using efficient multi-row insert
        rows_loaded = dataframe.to_sql(
            table_name,
            engine,
            schema='staging',
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000  # Insert in chunks of 1000 rows for optimal performance
        )

        logger.info(f"Loaded {len(dataframe)} rows into {full_table_name}")
        return len(dataframe)

    except Exception as e:
        logger.error(f"Error loading data to {full_table_name}: {e}")
        raise


def execute_transformations() -> bool:
    """
    Execute SQL transformation script to move data from staging to analytics
    Optimized to run in a single transaction for better performance

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Starting data transformation phase")

        # Read transform.sql file
        script_path = os.path.join(os.path.dirname(__file__), 'transform.sql')

        if not os.path.exists(script_path):
            logger.error(f"Transform script not found: {script_path}")
            return False

        with open(script_path, 'r') as f:
            sql_script = f.read()

        # Execute transformation script in a single transaction for better performance
        engine = get_db_engine()

        with engine.connect() as conn:
            # Execute the transformation script
            # Use execution_options to improve performance
            conn = conn.execution_options(isolation_level="READ COMMITTED")
            with conn.begin():
                conn.execute(text(sql_script))
                logger.info("Transformation script executed successfully")

        logger.info("Data transformation phase completed")
        return True

    except Exception as e:
        logger.error(f"Error during transformation: {e}")
        return False


if __name__ == "__main__":
    try:
        logger.info("Starting Financial Dashboard Data Pipeline")

        # Test database connection
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")

        # Data Extraction Phase
        logger.info("=== Starting Data Extraction Phase ===")

        # Extract stock data
        stock_df = extract_stock_data(BASE_STOCK_SYMBOLS)
        if not stock_df.empty:
            load_to_staging(stock_df, 'raw_stock_prices')

        # Extract news data
        news_df = extract_news_data(BASE_STOCK_SYMBOLS)
        if not news_df.empty:
            load_to_staging(news_df, 'raw_news_articles')

        # Extract economic data
        econ_df = extract_econ_data(ECONOMIC_SERIES)
        if not econ_df.empty:
            load_to_staging(econ_df, 'raw_econ_data')

        logger.info("=== Data Extraction Phase Complete ===")

        # Data Transformation Phase
        logger.info("=== Starting Data Transformation Phase ===")

        if execute_transformations():
            logger.info("=== Data Transformation Phase Complete ===")
        else:
            logger.error("Data transformation failed")
            raise Exception("Transformation phase failed")

        logger.info("Financial Dashboard Data Pipeline completed successfully")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise