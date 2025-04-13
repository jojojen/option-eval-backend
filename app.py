from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Black-Scholes formula to calculate option price
def black_scholes(S, K, T, r, sigma, option_type='call'):
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == 'call':
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    elif option_type == 'put':
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    else:
        raise ValueError("option_type must be 'call' or 'put'")
    return price

def norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

# Get historical volatility
def get_historical_volatility(ticker):
    logger.info(f"Fetching historical data for {ticker}")
    stock = yf.Ticker(ticker)
    hist = stock.history(period="30d")
    closes = hist['Close'].values
    returns = np.log(closes[1:] / closes[:-1])
    sigma_daily = np.std(returns)
    logger.info(f"Calculated daily volatility (sigma_daily): {sigma_daily}")
    return sigma_daily

# Get risk-free rate (10-year Treasury yield)
def get_risk_free_rate():
    logger.info("Fetching 10-year Treasury yield")
    treasury = yf.Ticker("^TNX")
    hist = treasury.history(period="1d")
    if not hist.empty:
        rate = hist['Close'].iloc[-1] / 100  # Convert to decimal
        logger.info(f"Latest 10-year Treasury yield: {rate}")
        return rate
    else:
        logger.warning("Failed to fetch Treasury yield, using default value")
        return 0.01  # Default value 1%

# Get filtered options data
def get_filtered_options(ticker, min_days=5, min_volume=10, min_open_interest=10, max_theoretical_price=2.0):
    logger.info(f"Fetching options data for {ticker}")
    stock = yf.Ticker(ticker)
    S = stock.history(period='1d')['Close'].iloc[-1]
    logger.info(f"Current stock price (S): {S}")
    expiration_dates = stock.options
    today = datetime.now()
    min_expiration = today + timedelta(days=min_days * 7 / 5)
    valid_dates = [date for date in expiration_dates if datetime.strptime(date, '%Y-%m-%d') >= min_expiration]
    logger.info(f"Valid expiration dates: {valid_dates}")
    calls_list = []
    puts_list = []
    for date in valid_dates:
        chain = stock.option_chain(date)
        calls = chain.calls
        puts = chain.puts
        calls['expiration'] = date
        puts['expiration'] = date
        calls_list.append(calls)
        puts_list.append(puts)
    all_calls = pd.concat(calls_list, ignore_index=True)
    all_puts = pd.concat(puts_list, ignore_index=True)
    # Filter by liquidity
    all_calls = all_calls[(all_calls['volume'] > min_volume) & (all_calls['openInterest'] > min_open_interest)]
    all_puts = all_puts[(all_puts['volume'] > min_volume) & (all_puts['openInterest'] > min_open_interest)]
    # Calculate theoretical price
    r = get_risk_free_rate()
    sigma_daily = get_historical_volatility(ticker)
    sigma_annual = sigma_daily * math.sqrt(252)
    logger.info(f"Annualized volatility (sigma_annual): {sigma_annual}")
    all_calls['theoretical_price'] = all_calls.apply(
        lambda row: black_scholes(S, row['strike'], (datetime.strptime(row['expiration'], '%Y-%m-%d') - today).days / 365, r, sigma_annual, 'call'), axis=1)
    all_puts['theoretical_price'] = all_puts.apply(
        lambda row: black_scholes(S, row['strike'], (datetime.strptime(row['expiration'], '%Y-%m-%d') - today).days / 365, r, sigma_annual, 'put'), axis=1)
    # Filter by theoretical price
    filtered_calls = all_calls[all_calls['theoretical_price'] <= max_theoretical_price]
    filtered_puts = all_puts[all_puts['theoretical_price'] <= max_theoretical_price]
    return filtered_calls, filtered_puts, S, r, sigma_annual

# Select out-of-the-money (OTM) options
def select_otm_options(calls, puts, S):
    otm_calls = calls[calls['strike'] > S]
    otm_puts = puts[puts['strike'] < S]
    call_selected = otm_calls.iloc[(otm_calls['strike'] - S).abs().argmin()] if not otm_calls.empty else None
    put_selected = otm_puts.iloc[(S - otm_puts['strike']).abs().argmin()] if not otm_puts.empty else None
    return call_selected, put_selected

# Main function: Get option recommendation
def get_option_recommendation(ticker, min_days=5, min_volume=10, min_open_interest=10, max_theoretical_price=2.0):
    calls, puts, S, r, sigma_annual = get_filtered_options(ticker, min_days, min_volume, min_open_interest, max_theoretical_price)
    call_selected, put_selected = select_otm_options(calls, puts, S)
    
    # Handle call option
    if call_selected is not None:
        exp_date = datetime.strptime(call_selected['expiration'], '%Y-%m-%d').strftime('%m/%d/%y')
        call_desc = f"{exp_date} {call_selected['strike']:.2f} Call"
        call_result = {
            'ask': call_selected['ask'],
            'bid': call_selected['bid'],
            'last': call_selected['lastPrice'],
            'desc': call_desc,
            'expiration': call_selected['expiration'],
            'strike': call_selected['strike'],
            'theoretical_price': call_selected['theoretical_price']
        }
    else:
        call_result = None
        logger.warning("No qualifying call options found")
    
    # Handle put option
    if put_selected is not None:
        exp_date = datetime.strptime(put_selected['expiration'], '%Y-%m-%d').strftime('%m/%d/%y')
        put_desc = f"{exp_date} {put_selected['strike']:.2f} Put"
        put_result = {
            'ask': put_selected['ask'],
            'bid': put_selected['bid'],
            'last': put_selected['lastPrice'],
            'desc': put_desc,
            'expiration': put_selected['expiration'],
            'strike': put_selected['strike'],
            'theoretical_price': put_selected['theoretical_price']
        }
    else:
        put_result = None
        logger.warning("No qualifying put options found")
    
    # Calculation summary
    cal_summary = {
        'risk_free_rate': r,           # Risk-free rate (Treasury yield)
        'annualized_volatility': sigma_annual,  # Annualized volatility
        'stock_price': S              # Current stock price
    }
    logger.info(f"Calculation summary: {cal_summary}")
    
    return {
        'call': call_result,
        'put': put_result,
        'cal_summary': cal_summary
    }

# Flask route
@app.route('/api/options', methods=['POST'])
def get_options():
    data = request.json
    if not data or 'ticker' not in data:
        return jsonify({'error': 'Ticker is required'}), 400
    ticker = data['ticker']
    min_days = data.get('min_days', 5)
    min_volume = data.get('min_volume', 10)
    min_open_interest = data.get('min_open_interest', 10)
    max_theoretical_price = data.get('max_theoretical_price', 2.0)
    result = get_option_recommendation(ticker, min_days, min_volume, min_open_interest, max_theoretical_price)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)