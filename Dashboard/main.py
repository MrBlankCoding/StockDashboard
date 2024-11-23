# app.py
from flask import Flask, render_template, jsonify, request
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Alpha Vantage API configuration
ALPHA_VANTAGE_API_KEY = os.getenv('API_KEY')
BASE_URL = 'https://www.alphavantage.co/query'

def get_historical_data(symbol):
    try:
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'apikey': ALPHA_VANTAGE_API_KEY,
            'outputsize': 'compact'  # Returns the latest 100 data points
        }
        
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if 'Time Series (Daily)' in data:
            historical_data = []
            time_series = data['Time Series (Daily)']
            
            # Convert to list and sort by date
            dates = sorted(time_series.keys(), reverse=True)[:30]  # Get last 30 days
            
            for date in dates:
                historical_data.append({
                    'date': date,
                    'price': float(time_series[date]['4. close'])
                })
            
            return historical_data
        return None
        
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {str(e)}")
        return None

def get_company_overview(symbol):
    try:
        params = {
            'function': 'OVERVIEW',
            'symbol': symbol,
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        
        response = requests.get(BASE_URL, params=params)
        return response.json()
        
    except Exception as e:
        print(f"Error fetching company overview for {symbol}: {str(e)}")
        return {}

def get_quote(symbol):
    try:
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if 'Global Quote' in data:
            return data['Global Quote']
        return None
        
    except Exception as e:
        print(f"Error fetching quote for {symbol}: {str(e)}")
        return None

def get_stock_data(symbol):
    try:
        # Get current quote
        quote = get_quote(symbol)
        if not quote:
            return None
            
        # Get company overview
        overview = get_company_overview(symbol)
        
        # Get historical data
        historical_data = get_historical_data(symbol)
        
        # Create a response with available data
        response = {
            'symbol': symbol,
            'current_price': float(quote['05. price']),
            'change': float(quote['09. change']),
            'percent_change': float(quote['10. change percent'].rstrip('%')),
            'high': float(quote['03. high']),
            'low': float(quote['04. low']),
            'open': float(quote['02. open']),
            'prev_close': float(quote['08. previous close']),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'company_name': overview.get('Name', ''),
            'currency': 'USD',
            'exchange': overview.get('Exchange', ''),
            'industry': overview.get('Industry', ''),
            'historical_data': historical_data
        }
        
        return response
        
    except Exception as e:
        print(f"Error fetching data for {symbol}: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stock/<symbol>')
def get_stock(symbol):
    data = get_stock_data(symbol.upper())
    if data:
        return jsonify({'success': True, 'data': data})
    return jsonify({'success': False, 'error': 'Failed to fetch stock data'})

@app.route('/api/search')
def search_stocks():
    query = request.args.get('q', '')
    try:
        params = {
            'function': 'SYMBOL_SEARCH',
            'keywords': query,
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if 'bestMatches' in data:
            results = []
            for match in data['bestMatches'][:5]:  # Limit to top 5 results
                results.append({
                    'symbol': match['1. symbol'],
                    'description': match['2. name']
                })
            return jsonify({
                'success': True,
                'results': results
            })
        return jsonify({'success': False, 'error': 'No matches found'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)