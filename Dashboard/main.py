from flask import Flask, render_template, request, jsonify
import os
import logging
from polygon import RESTClient
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG,  # Set to DEBUG for detailed output
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.StreamHandler()])  # Output logs to the console

app = Flask(__name__)

# Replace with your Polygon.io API key
POLYGON_API_KEY = "rfyFIj2sCGjr8RhHOU5zgS6Hb7lTGl2p"
client = RESTClient(POLYGON_API_KEY)

@app.route('/')
def index():
    app.logger.info("Rendering index page.")
    return render_template('index.html')

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol):
    try:
        app.logger.debug(f"Received request for stock data: {symbol}")
        
        # Get today's date and yesterday's date
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        app.logger.debug(f"Date range: {start_date} to {end_date}")
        
        # Fetch aggregates for the date range
        aggs = client.get_aggs(
            symbol,
            1,
            "day",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
        app.logger.debug(f"Aggregates data fetched: {len(aggs)} entries.")
        
        # Fetch company details
        ticker_details = client.get_ticker_details(symbol)
        app.logger.debug(f"Company details fetched: {ticker_details.name}")
        
        # Prepare response
        response = {
            "success": True,
            "data": {
                "aggs": [{"date": agg.timestamp, "close": agg.close, 
                         "high": agg.high, "low": agg.low, 
                         "volume": agg.volume} for agg in aggs],
                "details": {
                    "name": ticker_details.name,
                    "market": ticker_details.market,
                    "locale": ticker_details.locale
                }
            }
        }
        app.logger.info(f"Response prepared successfully for symbol: {symbol}")
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f"Error while fetching stock data for {symbol}: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.logger.info("Starting Flask application.")
    app.run(debug=True)
