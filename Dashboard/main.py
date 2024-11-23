from flask import Flask, render_template, request, jsonify
from polygon import RESTClient
from datetime import datetime, timedelta

app = Flask(__name__)

POLYGON_API_KEY = "rfyFIj2sCGjr8RhHOU5zgS6Hb7lTGl2p"
client = RESTClient(POLYGON_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol):
    try:
        # Get time range from query parameter
        time_range = request.args.get('range', '1W')  # Default to 1 week
        
        end_date = datetime.now()
        
        # Calculate start date based on time range
        if time_range == '1D':
            start_date = end_date - timedelta(days=1)
            multiplier = 5  # 5-minute intervals
            timespan = "minute"
        elif time_range == '1W':
            start_date = end_date - timedelta(weeks=1)
            multiplier = 1
            timespan = "day"
        elif time_range == '1M':
            start_date = end_date - timedelta(days=30)
            multiplier = 1
            timespan = "day"
        elif time_range == '1Y':
            start_date = end_date - timedelta(days=365)
            multiplier = 1
            timespan = "day"
        else:  # All time (max 5 years)
            start_date = end_date - timedelta(days=365*5)
            multiplier = 1
            timespan = "week"
        
        # Fetch aggregates for the date range
        aggs = client.get_aggs(
            symbol,
            multiplier,
            timespan,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
        
        # Fetch company details
        ticker_details = client.get_ticker_details(symbol)
        
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
        return jsonify(response)
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)