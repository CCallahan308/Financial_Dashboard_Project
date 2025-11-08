#!/usr/bin/env python3
"""
Financial Dashboard Flask Application
Web interface displaying financial analytics data from the star schema
"""

import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
import plotly.graph_objects as go
import plotly.utils
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def get_analytics_data():
    """
    Fetch stock price data for dashboard visualization

    Returns:
        DataFrame-like result with stock price data
    """
    query = """
    SELECT
        dd.full_date,
        ds.symbol,
        ds.company_name,
        fp.close_price,
        fp.volume
    FROM analytics.fact_prices fp
    JOIN analytics.dim_date dd ON fp.date_key = dd.date_key
    JOIN analytics.dim_security ds ON fp.security_key = ds.security_key
    WHERE dd.full_date >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY dd.full_date, ds.symbol;
    """

    with engine.connect() as conn:
        result = conn.execute(text(query))
        data = result.fetchall()

    return data


def get_news_data():
    """
    Fetch recent news articles for dashboard

    Returns:
        List of recent news articles
    """
    query = """
    SELECT
        fn.title,
        fn.description,
        fn.url,
        fn.source_name,
        fn.sentiment_score,
        ds.symbol,
        dd.full_date
    FROM analytics.fact_news fn
    JOIN analytics.dim_date dd ON fn.date_key = dd.date_key
    JOIN analytics.dim_security ds ON fn.security_key = ds.security_key
    WHERE dd.full_date >= CURRENT_DATE - INTERVAL '7 days'
    ORDER BY dd.full_date DESC
    LIMIT 10;
    """

    with engine.connect() as conn:
        result = conn.execute(text(query))
        data = result.fetchall()

    return data


def get_economic_data():
    """
    Fetch economic indicators data for dashboard

    Returns:
        Economic indicators data
    """
    query = """
    SELECT
        dei.indicator_name,
        fe.value,
        fe.change_percent,
        dd.full_date
    FROM analytics.fact_economics fe
    JOIN analytics.dim_date dd ON fe.date_key = dd.date_key
    JOIN analytics.dim_economic_indicator dei ON fe.indicator_key = dei.indicator_key
    WHERE dd.full_date >= CURRENT_DATE - INTERVAL '90 days'
    ORDER BY dd.full_date DESC, dei.indicator_name;
    """

    with engine.connect() as conn:
        result = conn.execute(text(query))
        data = result.fetchall()

    return data


def get_summary_metrics():
    """
    Calculate key metrics for dashboard summary cards

    Returns:
        Dictionary with key metrics
    """
    query = """
    WITH latest_prices AS (
        SELECT DISTINCT ON (ds.symbol)
            ds.symbol,
            ds.company_name,
            fp.close_price,
            dd.full_date
        FROM analytics.fact_prices fp
        JOIN analytics.dim_date dd ON fp.date_key = dd.date_key
        JOIN analytics.dim_security ds ON fp.security_key = ds.security_key
        ORDER BY ds.symbol, dd.full_date DESC
    ),
    price_changes AS (
        SELECT
            lp.symbol,
            lp.close_price as current_price,
            fp.close_price as previous_price,
            ((lp.close_price - fp.close_price) / fp.close_price) * 100 as price_change
        FROM latest_prices lp
        JOIN analytics.fact_prices fp ON lp.symbol = (
            SELECT ds.symbol FROM analytics.dim_security ds WHERE ds.security_key = fp.security_key
        )
        JOIN analytics.dim_date dd ON fp.date_key = dd.date_key
        WHERE dd.full_date = lp.full_date - INTERVAL '1 day'
    ),
    sentiment as (
        SELECT AVG(sentiment_score) as avg_sentiment FROM analytics.fact_news
    )
    SELECT
        (SELECT COUNT(*) FROM analytics.dim_security) as total_securities,
        SUM(CASE WHEN pc.price_change > 0 THEN 1 ELSE 0 END) as gainers,
        SUM(CASE WHEN pc.price_change < 0 THEN 1 ELSE 0 END) as losers,
        SUM(CASE WHEN pc.price_change = 0 THEN 1 ELSE 0 END) as unchanged,
        AVG(CASE WHEN pc.price_change > 0 THEN pc.price_change ELSE NULL END) as avg_gain,
        AVG(CASE WHEN pc.price_change < 0 THEN pc.price_change ELSE NULL END) as avg_loss,
        (SELECT avg_sentiment FROM sentiment)
    FROM price_changes pc;
    """

    with engine.connect() as conn:
        result = conn.execute(text(query))
        data = result.fetchone()

    return {
        'total_securities': data.total_securities if data else 0,
        'gainers': data.gainers if data else 0,
        'losers': data.losers if data else 0,
        'unchanged': data.unchanged if data else 0,
        'avg_gain': round(data.avg_gain, 2) if data and data.avg_gain else 0,
        'avg_loss': round(data.avg_loss, 2) if data and data.avg_loss else 0,
        'avg_sentiment': round(data.avg_sentiment, 2) if data and data.avg_sentiment else 0
    }


def create_price_chart(data):
    """
    Create interactive Plotly chart for stock prices

    Args:
        data: Stock price data from database

    Returns:
        Plotly JSON representation of the chart
    """
    if not data:
        return json.dumps({})

    # Organize data by symbol
    symbols = {}
    for row in data:
        symbol = row.symbol
        if symbol not in symbols:
            symbols[symbol] = {'dates': [], 'prices': [], 'volumes': []}
        symbols[symbol]['dates'].append(row.full_date.strftime('%Y-%m-%d'))
        symbols[symbol]['prices'].append(float(row.close_price))
        symbols[symbol]['volumes'].append(int(row.volume))

    # Create figure with secondary y-axis for volume
    fig = go.Figure()

    # Add price lines for each symbol
    for symbol, data_dict in symbols.items():
        fig.add_trace(go.Scatter(
            x=data_dict['dates'],
            y=data_dict['prices'],
            mode='lines+markers',
            name=f'{symbol} Price',
            line=dict(width=2),
            hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>'
        ))

    fig.update_layout(
        title='Stock Price Trends (Last 30 Days)',
        xaxis_title='Date',
        yaxis_title='Stock Price ($)',
        hovermode='x unified',
        template='plotly_white',
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )

    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def create_volume_chart(data):
    """
    Create interactive Plotly chart for trading volume

    Args:
        data: Stock price data from database

    Returns:
        Plotly JSON representation of the chart
    """
    if not data:
        return json.dumps({})

    # Organize data by symbol
    symbols = {}
    for row in data:
        symbol = row.symbol
        if symbol not in symbols:
            symbols[symbol] = {'dates': [], 'volumes': []}
        symbols[symbol]['dates'].append(row.full_date.strftime('%Y-%m-%d'))
        symbols[symbol]['volumes'].append(int(row.volume))

    # Create figure
    fig = go.Figure()

    # Add volume bars for each symbol
    for symbol, data_dict in symbols.items():
        fig.add_trace(go.Bar(
            x=data_dict['dates'],
            y=data_dict['volumes'],
            name=f'{symbol} Volume',
            hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Volume: %{y:,.0f}<extra></extra>'
        ))

    fig.update_layout(
        title='Trading Volume (Last 30 Days)',
        xaxis_title='Date',
        yaxis_title='Volume',
        barmode='group',
        template='plotly_white',
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )

    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


@app.route('/')
def dashboard():
    """
    Main dashboard page route
    """
    try:
        # Fetch data from analytics database
        stock_data = get_analytics_data()
        news_data = get_news_data()
        economic_data = get_economic_data()
        summary_metrics = get_summary_metrics()

        # Create charts
        price_chart = create_price_chart(stock_data)
        volume_chart = create_volume_chart(stock_data)

        return render_template('index.html',
                           price_chart=price_chart,
                           volume_chart=volume_chart,
                           news_data=news_data,
                           economic_data=economic_data,
                           summary_metrics=summary_metrics)

    except Exception as e:
        app.logger.error(f"Error loading dashboard: {e}")
        return render_template('error.html', error=str(e)), 500


@app.route('/api/refresh')
def refresh_data():
    """
    API endpoint to refresh dashboard data
    """
    try:
        # Fetch fresh data
        stock_data = get_analytics_data()
        news_data = get_news_data()
        economic_data = get_economic_data()
        summary_metrics = get_summary_metrics()

        # Create fresh charts
        price_chart = create_price_chart(stock_data)
        volume_chart = create_volume_chart(stock_data)

        return jsonify({
            'success': True,
            'price_chart': json.loads(price_chart),
            'volume_chart': json.loads(volume_chart),
            'summary_metrics': summary_metrics,
            'news_count': len(news_data),
            'economic_count': len(economic_data)
        })

    except Exception as e:
        app.logger.error(f"Error refreshing data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/health')
def health_check():
    """
    Health check endpoint
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'database': 'disconnected', 'error': str(e)}), 500


if __name__ == '__main__':
    # Run Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)