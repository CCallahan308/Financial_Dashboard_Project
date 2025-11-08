"""
Python Quantitative Model with yfinance

A modular Python-based quantitative analysis tool that accepts any stock ticker as input,
fetches market data using yfinance, calculates technical and fundamental factors,
performs options-based metrics analysis, and generates consolidated trading signals.

Author: Claude Code Implementation
Date: 2024
"""

import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from py_vollib.black_scholes import black_scholes
from py_vollib.black_scholes.greeks import analytical
from datetime import datetime, timedelta
import warnings
import logging
import time
from typing import Dict, Any, Optional, Tuple

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QuantitativeAnalyzer:
    """
    A comprehensive quantitative analysis tool for stocks that combines technical indicators,
    fundamental metrics, and options analysis to generate trading signals.

    Main method: get_quant_analysis(ticker_symbol) returns complete analysis dictionary.
    """

    def __init__(self, risk_free_rate: float = 0.02, historical_period: str = "1y"):
        """
        Initialize the QuantitativeAnalyzer.

        Args:
            risk_free_rate (float): Risk-free rate for options calculations (default: 2%)
            historical_period (str): Period for historical data (default: "1y")
        """
        self.risk_free_rate = risk_free_rate
        self.historical_period = historical_period

        # Signal thresholds
        self.signal_thresholds = {
            'STRONG_BUY': 4,
            'BUY': 2,
            'NEUTRAL': (-1, 1),
            'SELL': -2,
            'STRONG_SELL': -4
        }

        # Data quality filters
        self.outlier_threshold = 3.0  # Standard deviations

        logger.info(f"QuantitativeAnalyzer initialized with risk_free_rate={risk_free_rate}")

    def get_quant_analysis(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Main method - performs complete quantitative analysis for a ticker.

        Args:
            ticker_symbol (str): Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Dict containing comprehensive analysis with technical indicators,
            fundamental metrics, options analysis, and trading signals.
        """
        start_time = time.time()
        logger.info(f"Starting quantitative analysis for {ticker_symbol}")

        try:
            # Initialize result structure
            analysis = {
                'ticker': ticker_symbol.upper(),
                'current_price': None,
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'technical_indicators': {},
                'fundamental_metrics': {},
                'options_metrics': {'options_data_available': False},
                'trading_signal': {},
                'data_quality': {
                    'technical_data_complete': False,
                    'fundamental_data_complete': False,
                    'options_data_complete': False,
                    'warnings': []
                }
            }

            # Step 1: Fetch market data
            market_data = self._fetch_market_data(ticker_symbol)
            if market_data is None:
                analysis['data_quality']['warnings'].append("Failed to fetch market data")
                return analysis

            analysis['current_price'] = market_data['current_price']

            # Step 2: Calculate technical indicators
            if 'historical_data' in market_data:
                technical_indicators = self._calculate_technical_indicators(market_data['historical_data'])
                if technical_indicators:
                    analysis['technical_indicators'] = technical_indicators
                    analysis['data_quality']['technical_data_complete'] = True
                else:
                    analysis['data_quality']['warnings'].append("Failed to calculate technical indicators")

            # Step 3: Get fundamental metrics
            if 'ticker_info' in market_data:
                fundamental_metrics = self._get_fundamental_metrics(market_data['ticker_info'])
                if fundamental_metrics:
                    analysis['fundamental_metrics'] = fundamental_metrics
                    analysis['data_quality']['fundamental_data_complete'] = True
                else:
                    analysis['data_quality']['warnings'].append("Failed to get fundamental metrics")

            # Step 4: Analyze options chain
            options_metrics = self._analyze_options_chain(ticker_symbol, market_data['current_price'])
            if options_metrics:
                analysis['options_metrics'] = options_metrics
                analysis['data_quality']['options_data_complete'] = True

            # Step 5: Generate trading signals
            trading_signal = self._generate_signals(analysis)
            analysis['trading_signal'] = trading_signal

            # Calculate execution time
            execution_time = time.time() - start_time
            logger.info(f"Analysis completed for {ticker_symbol} in {execution_time:.2f} seconds")

            return analysis

        except Exception as e:
            logger.error(f"Error in get_quant_analysis for {ticker_symbol}: {str(e)}")
            return {
                'ticker': ticker_symbol.upper(),
                'error': str(e),
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_quality': {'warnings': [f"Analysis failed: {str(e)}"]}
            }

    def _fetch_market_data(self, ticker_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch all required market data from yfinance.

        Args:
            ticker_symbol (str): Stock ticker symbol

        Returns:
            Dict containing current price, historical data, and ticker info, or None if failed
        """
        try:
            ticker = yf.Ticker(ticker_symbol)

            # Get current price
            current_data = ticker.history(period="2d")
            if current_data.empty:
                logger.error(f"No current data available for {ticker_symbol}")
                return None

            current_price = current_data['Close'].iloc[-1]
            if current_price <= 0:
                logger.error(f"Invalid current price for {ticker_symbol}: {current_price}")
                return None

            # Get historical data
            historical_data = ticker.history(period=self.historical_period)
            if len(historical_data) < 200:
                logger.warning(f"Insufficient historical data for {ticker_symbol}: {len(historical_data)} days")

            # Get ticker info
            ticker_info = ticker.info

            return {
                'current_price': current_price,
                'historical_data': historical_data,
                'ticker_info': ticker_info,
                'options_available': len(ticker.options) > 0 if hasattr(ticker, 'options') else False
            }

        except Exception as e:
            logger.error(f"Error fetching market data for {ticker_symbol}: {str(e)}")
            return None

    def _calculate_technical_indicators(self, historical_data: pd.DataFrame) -> Optional[Dict[str, float]]:
        """
        Calculate all technical indicators using pandas-ta.

        Args:
            historical_data (pd.DataFrame): OHLCV data from yfinance

        Returns:
            Dict containing all technical indicator values
        """
        try:
            if len(historical_data) < 50:
                logger.warning("Insufficient data for technical indicators")
                return None

            # Make a copy to avoid modifying original data
            df = historical_data.copy()

            # Calculate required indicators using pandas-ta
            df.ta.sma(length=50, append=True)
            df.ta.sma(length=200, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            df.ta.bbands(length=20, std=2, append=True)
            df.ta.atr(length=14, append=True)

            # Extract current values (last row)
            latest_data = df.iloc[-1]

            technical_indicators = {}

            # Moving Averages
            if 'SMA_50' in latest_data and not pd.isna(latest_data['SMA_50']):
                technical_indicators['sma_50'] = float(latest_data['SMA_50'])

            if 'SMA_200' in latest_data and not pd.isna(latest_data['SMA_200']):
                technical_indicators['sma_200'] = float(latest_data['SMA_200'])

            # RSI
            if 'RSI_14' in latest_data and not pd.isna(latest_data['RSI_14']):
                technical_indicators['rsi_14'] = float(latest_data['RSI_14'])

            # MACD
            if 'MACD_12_26_9' in latest_data and not pd.isna(latest_data['MACD_12_26_9']):
                technical_indicators['macd'] = float(latest_data['MACD_12_26_9'])

            if 'MACDs_12_26_9' in latest_data and not pd.isna(latest_data['MACDs_12_26_9']):
                technical_indicators['macd_signal'] = float(latest_data['MACDs_12_26_9'])

            if 'MACDh_12_26_9' in latest_data and not pd.isna(latest_data['MACDh_12_26_9']):
                technical_indicators['macd_histogram'] = float(latest_data['MACDh_12_26_9'])

            # Bollinger Bands
            if 'BBL_20_2.0' in latest_data and not pd.isna(latest_data['BBL_20_2.0']):
                technical_indicators['bb_lower'] = float(latest_data['BBL_20_2.0'])

            if 'BBM_20_2.0' in latest_data and not pd.isna(latest_data['BBM_20_2.0']):
                technical_indicators['bb_middle'] = float(latest_data['BBM_20_2.0'])

            if 'BBU_20_2.0' in latest_data and not pd.isna(latest_data['BBU_20_2.0']):
                technical_indicators['bb_upper'] = float(latest_data['BBU_20_2.0'])

            # ATR
            if 'ATRr_14' in latest_data and not pd.isna(latest_data['ATRr_14']):
                technical_indicators['atr_14'] = float(latest_data['ATRr_14'])

            return technical_indicators if technical_indicators else None

        except Exception as e:
            logger.error(f"Error calculating technical indicators: {str(e)}")
            return None

    def _get_fundamental_metrics(self, ticker_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract and validate fundamental metrics from ticker.info.

        Args:
            ticker_info (Dict): ticker.info dictionary from yfinance

        Returns:
            Dict containing fundamental metrics with validation
        """
        try:
            fundamental_metrics = {}

            # Forward P/E Ratio
            forward_pe = ticker_info.get('forwardPE')
            if forward_pe is not None and 0 < forward_pe <= 1000:
                fundamental_metrics['forward_pe'] = float(forward_pe)
            else:
                logger.warning("Invalid or missing forward P/E ratio")
                fundamental_metrics['forward_pe'] = None

            # Price-to-Book Ratio
            price_to_book = ticker_info.get('priceToBook')
            if price_to_book is not None and 0 < price_to_book <= 100:
                fundamental_metrics['price_to_book'] = float(price_to_book)
            else:
                logger.warning("Invalid or missing price-to-book ratio")
                fundamental_metrics['price_to_book'] = None

            # Dividend Yield
            dividend_yield = ticker_info.get('dividendYield')
            if dividend_yield is not None and 0 <= dividend_yield <= 1:
                fundamental_metrics['dividend_yield'] = float(dividend_yield)
            else:
                logger.warning("Invalid or missing dividend yield")
                fundamental_metrics['dividend_yield'] = None

            return fundamental_metrics

        except Exception as e:
            logger.error(f"Error extracting fundamental metrics: {str(e)}")
            return None

    def _analyze_options_chain(self, ticker_symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """
        Analyze options data and calculate Greeks using py_vollib.

        Args:
            ticker_symbol (str): Stock ticker symbol
            current_price (float): Current stock price

        Returns:
            Dict containing options-based metrics and Greeks
        """
        try:
            ticker = yf.Ticker(ticker_symbol)

            # Check if options data is available
            if not hasattr(ticker, 'options') or len(ticker.options) == 0:
                logger.info(f"No options data available for {ticker_symbol}")
                return {'options_data_available': False}

            expirations = ticker.options

            # Filter expirations (exclude those < 1 day away)
            valid_expirations = []
            today = datetime.now().date()

            for exp_date in expirations:
                exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d').date()
                days_to_expiry = (exp_datetime - today).days
                if 1 <= days_to_expiry <= 365:  # Valid range: 1 day to 1 year
                    valid_expirations.append((exp_date, days_to_expiry))

            if not valid_expirations:
                logger.info(f"No valid options expirations for {ticker_symbol}")
                return {'options_data_available': False}

            # Sort by days to expiry and take nearest 2
            valid_expirations.sort(key=lambda x: x[1])
            nearest_expirations = valid_expirations[:2]

            options_metrics = {
                'options_data_available': True,
                'nearest_expiry': nearest_expirations[0][0],
                'atm_strike': None
            }

            # Analyze nearest expiration
            exp_date, days_to_expiry = nearest_expirations[0]
            time_to_expiry = days_to_expiry / 365.0

            try:
                option_chain = ticker.option_chain(exp_date)
                calls = option_chain.calls
                puts = option_chain.puts

                # Find ATM strike (closest to current price)
                all_strikes = pd.concat([calls['strike'], puts['strike']]).unique()
                atm_strike = all_strikes[np.argmin(np.abs(all_strikes - current_price))]
                options_metrics['atm_strike'] = float(atm_strike)

                # Extract ATM options data
                atm_call = calls[calls['strike'] == atm_strike]
                atm_put = puts[puts['strike'] == atm_strike]

                if not atm_call.empty and not atm_put.empty:
                    call_data = atm_call.iloc[0]
                    put_data = atm_put.iloc[0]

                    # Get implied volatilities
                    call_iv = call_data.get('impliedVolatility', 0)
                    put_iv = put_data.get('impliedVolatility', 0)

                    options_metrics['call_iv'] = float(call_iv) if not pd.isna(call_iv) else None
                    options_metrics['put_iv'] = float(put_iv) if not pd.isna(put_iv) else None

                    # Calculate Greeks for ATM options
                    try:
                        # Use average IV or fallback to historical volatility
                        sigma = (call_iv + put_iv) / 2 if call_iv and put_iv else 0.25  # 25% default

                        # Calculate Greeks for ATM call
                        call_delta = analytical.delta('c', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)
                        call_gamma = analytical.gamma('c', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)
                        call_vega = analytical.vega('c', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)
                        call_theta = analytical.theta('c', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)

                        # Calculate Greeks for ATM put
                        put_delta = analytical.delta('p', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)
                        put_gamma = analytical.gamma('p', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)
                        put_vega = analytical.vega('p', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)
                        put_theta = analytical.theta('p', current_price, atm_strike, time_to_expiry, self.risk_free_rate, sigma)

                        options_metrics.update({
                            'call_delta': float(call_delta),
                            'call_gamma': float(call_gamma),
                            'call_vega': float(call_vega),
                            'call_theta': float(call_theta),
                            'put_delta': float(put_delta),
                            'put_gamma': float(put_gamma),
                            'put_vega': float(put_vega),
                            'put_theta': float(put_theta)
                        })

                    except Exception as e:
                        logger.warning(f"Error calculating Greeks for {ticker_symbol}: {str(e)}")

                    # Calculate volume and OI metrics
                    total_call_volume = calls['volume'].fillna(0).sum()
                    total_put_volume = puts['volume'].fillna(0).sum()
                    total_call_oi = calls['openInterest'].fillna(0).sum()
                    total_put_oi = puts['openInterest'].fillna(0).sum()

                    # Calculate Put-Call ratios
                    put_call_volume_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 0
                    put_call_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0

                    # ATM strike specific metrics
                    atm_call_volume = call_data.get('volume', 0)
                    atm_put_volume = put_data.get('volume', 0)
                    atm_call_oi = call_data.get('openInterest', 0)
                    atm_put_oi = put_data.get('openInterest', 0)

                    options_metrics.update({
                        'put_call_volume_ratio': float(put_call_volume_ratio),
                        'put_call_oi_ratio': float(put_call_oi_ratio),
                        'atm_total_volume': float(atm_call_volume + atm_put_volume),
                        'atm_total_oi': float(atm_call_oi + atm_put_oi)
                    })

            except Exception as e:
                logger.warning(f"Error processing options chain for {ticker_symbol}: {str(e)}")
                return {'options_data_available': False}

            return options_metrics

        except Exception as e:
            logger.error(f"Error analyzing options chain for {ticker_symbol}: {str(e)}")
            return {'options_data_available': False}

    def _generate_signals(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate final trading signals based on all calculated factors.

        Args:
            analysis (Dict): Complete analysis data with all metrics

        Returns:
            Dict containing trading signal with confidence score and reasoning
        """
        try:
            scores = {
                'technical_score': 0.0,
                'options_score': 0.0,
                'fundamental_score': 0.0
            }
            reasoning = []

            # Technical momentum scoring (-2 to +2)
            current_price = analysis.get('current_price', 0)
            tech_indicators = analysis.get('technical_indicators', {})

            if 'sma_50' in tech_indicators and 'sma_200' in tech_indicators:
                # Trend analysis
                if current_price > tech_indicators['sma_200']:
                    scores['technical_score'] += 1.0
                    reasoning.append("Bullish trend: Price above 200-day SMA")
                elif current_price < tech_indicators['sma_200']:
                    scores['technical_score'] -= 1.0
                    reasoning.append("Bearish trend: Price below 200-day SMA")

                # Moving average crossover
                if tech_indicators['sma_50'] > tech_indicators['sma_200']:
                    scores['technical_score'] += 0.5
                    reasoning.append("Bullish momentum: 50-day SMA above 200-day SMA")
                else:
                    scores['technical_score'] -= 0.5
                    reasoning.append("Bearish momentum: 50-day SMA below 200-day SMA")

            # RSI analysis
            if 'rsi_14' in tech_indicators:
                rsi = tech_indicators['rsi_14']
                if rsi < 30:  # Oversold
                    scores['technical_score'] += 1.0
                    reasoning.append(f"Oversold conditions: RSI at {rsi:.1f}")
                elif rsi > 70:  # Overbought
                    scores['technical_score'] -= 1.0
                    reasoning.append(f"Overbought conditions: RSI at {rsi:.1f}")
                elif 40 <= rsi <= 60:  # Neutral zone
                    reasoning.append(f"Neutral RSI: {rsi:.1f}")

            # MACD analysis
            if 'macd_histogram' in tech_indicators:
                macd_hist = tech_indicators['macd_histogram']
                if macd_hist > 0:
                    scores['technical_score'] += 0.5
                    reasoning.append("Positive MACD momentum")
                else:
                    scores['technical_score'] -= 0.5
                    reasoning.append("Negative MACD momentum")

            # Options sentiment scoring (-2 to +2)
            options_metrics = analysis.get('options_metrics', {})
            if options_metrics.get('options_data_available', False):
                # Put-Call ratio analysis (contrarian indicator)
                put_call_ratio = options_metrics.get('put_call_volume_ratio', 1.0)
                if put_call_ratio > 1.2:  # High fear - contrarian buy
                    scores['options_score'] += 1.0
                    reasoning.append(f"Contrarian sentiment: High put-call ratio ({put_call_ratio:.2f})")
                elif put_call_ratio < 0.8:  # Low fear - contrarian sell
                    scores['options_score'] -= 1.0
                    reasoning.append(f"Contrarian sentiment: Low put-call ratio ({put_call_ratio:.2f})")

                # Implied volatility analysis
                call_iv = options_metrics.get('call_iv')
                if call_iv and call_iv > 0.3:  # High IV
                    scores['options_score'] += 0.5
                    reasoning.append("Elevated implied volatility (fear)")
                elif call_iv and call_iv < 0.15:  # Low IV
                    scores['options_score'] -= 0.5
                    reasoning.append("Low implied volatility (complacency)")

            # Fundamental quality scoring (-1 to +1)
            fund_metrics = analysis.get('fundamental_metrics', {})

            # P/E ratio valuation
            pe_ratio = fund_metrics.get('forward_pe')
            if pe_ratio and 5 <= pe_ratio <= 30:  # Reasonable valuation
                scores['fundamental_score'] += 0.5
                reasoning.append(f"Reasonable P/E ratio: {pe_ratio:.1f}")
            elif pe_ratio and pe_ratio > 30:  # Expensive
                scores['fundamental_score'] -= 0.5
                reasoning.append(f"High P/E ratio: {pe_ratio:.1f}")

            # P/B ratio
            pb_ratio = fund_metrics.get('price_to_book')
            if pb_ratio and pb_ratio < 3:  # Reasonable P/B
                scores['fundamental_score'] += 0.5
                reasoning.append(f"Reasonable P/B ratio: {pb_ratio:.1f}")

            # Dividend yield
            dividend_yield = fund_metrics.get('dividend_yield')
            if dividend_yield and dividend_yield > 0.02:  # > 2% dividend
                scores['fundamental_score'] += 0.5
                reasoning.append(f"Attractive dividend yield: {dividend_yield*100:.1f}%")

            # Calculate total score
            total_score = scores['technical_score'] + scores['options_score'] + scores['fundamental_score']

            # Determine signal based on total score
            signal = 'NEUTRAL'
            if total_score >= self.signal_thresholds['STRONG_BUY']:
                signal = 'STRONG_BUY'
            elif total_score >= self.signal_thresholds['BUY']:
                signal = 'BUY'
            elif total_score <= self.signal_thresholds['STRONG_SELL']:
                signal = 'STRONG_SELL'
            elif total_score <= self.signal_thresholds['SELL']:
                signal = 'SELL'

            return {
                'signal': signal,
                'confidence_score': float(total_score),
                'reasoning': reasoning,
                'technical_score': float(scores['technical_score']),
                'options_score': float(scores['options_score']),
                'fundamental_score': float(scores['fundamental_score'])
            }

        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
            return {
                'signal': 'NEUTRAL',
                'confidence_score': 0.0,
                'reasoning': [f"Error generating signal: {str(e)}"],
                'technical_score': 0.0,
                'options_score': 0.0,
                'fundamental_score': 0.0
            }


# Example usage at the bottom of the file
if __name__ == "__main__":
    """
    Example usage of the QuantitativeAnalyzer class.

    This section demonstrates how to use the analyzer and provides
    sample output for testing purposes.
    """

    # Initialize the analyzer
    analyzer = QuantitativeAnalyzer(risk_free_rate=0.02)

    # Example tickers to analyze
    tickers = ['AAPL', 'MSFT', 'GOOGL']

    print("=== Python Quantitative Model Analysis ===\n")

    for ticker in tickers:
        print(f"Analyzing {ticker}...")

        try:
            # Get comprehensive analysis
            analysis = analyzer.get_quant_analysis(ticker)

            # Display results
            print(f"\n--- {ticker} Analysis Results ---")
            print(f"Current Price: ${analysis.get('current_price', 'N/A'):.2f}")
            print(f"Analysis Time: {analysis.get('analysis_timestamp', 'N/A')}")

            # Technical indicators
            tech = analysis.get('technical_indicators', {})
            if tech:
                print(f"\nTechnical Indicators:")
                print(f"  50-day SMA: ${tech.get('sma_50', 'N/A'):.2f}")
                print(f"  200-day SMA: ${tech.get('sma_200', 'N/A'):.2f}")
                print(f"  RSI (14): {tech.get('rsi_14', 'N/A'):.1f}")
                print(f"  MACD: {tech.get('macd_histogram', 'N/A'):.3f}")

            # Fundamental metrics
            fund = analysis.get('fundamental_metrics', {})
            if fund:
                print(f"\nFundamental Metrics:")
                print(f"  Forward P/E: {fund.get('forward_pe', 'N/A'):.1f}")
                print(f"  P/B Ratio: {fund.get('price_to_book', 'N/A'):.1f}")
                print(f"  Dividend Yield: {fund.get('dividend_yield', 0)*100:.2f}%")

            # Options metrics
            options = analysis.get('options_metrics', {})
            if options.get('options_data_available', False):
                print(f"\nOptions Metrics:")
                print(f"  Nearest Expiry: {options.get('nearest_expiry', 'N/A')}")
                print(f"  ATM Strike: ${options.get('atm_strike', 'N/A'):.2f}")
                print(f"  Put-Call Ratio: {options.get('put_call_volume_ratio', 'N/A'):.2f}")
                if options.get('call_iv'):
                    print(f"  Call IV: {options.get('call_iv', 0)*100:.1f}%")

            # Trading signal
            signal = analysis.get('trading_signal', {})
            print(f"\nTrading Signal: {signal.get('signal', 'N/A')}")
            print(f"Confidence Score: {signal.get('confidence_score', 'N/A'):.2f}")

            if signal.get('reasoning'):
                print("Reasoning:")
                for reason in signal['reasoning']:
                    print(f"  • {reason}")

            # Data quality
            quality = analysis.get('data_quality', {})
            if quality.get('warnings'):
                print(f"\nWarnings:")
                for warning in quality['warnings']:
                    print(f"  • {warning}")

        except Exception as e:
            print(f"Error analyzing {ticker}: {str(e)}")

        print("\n" + "="*60 + "\n")

    print("Analysis complete!")
    print("\nNote: This is a demonstration of the quantitative analysis tool.")
    print("For production use, consider additional risk management and validation.")