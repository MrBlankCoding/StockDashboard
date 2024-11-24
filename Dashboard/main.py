from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from polygon import RESTClient
from datetime import datetime, timedelta
import yfinance as yf


# Flask App Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

# MongoDB Setup
uri = "mongodb+srv://Ethan:L0U3pJNymy9nP1Hr@stockdash.s9jnm.mongodb.net/?retryWrites=true&w=majority&appName=StockDash"
client = MongoClient(uri, server_api=ServerApi('1'))
mongo = client['StockDash']

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Polygon API Setup
polygon_client = RESTClient('rfyFIj2sCGjr8RhHOU5zgS6Hb7lTGl2p')


# User Class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data

    def get_id(self):
        return str(self.user_data['_id'])

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.users.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None


# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if mongo.users.find_one({'email': email}):
            flash('Email already exists')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        mongo.users.insert_one({
            'email': email,
            'password': hashed_password,
            'balance': 10000.0,  # Initial balance
            'portfolio': {},     # Portfolio will store {symbol: {'shares': count, 'avg_price': price}}
            'trade_history': []  # Store trade history
        })
        flash('Registration successful')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Authenticate user
        user_data = mongo.users.find_one({'email': email})
        if user_data and check_password_hash(user_data['password'], password):
            login_user(User(user_data))
            return redirect(url_for('dashboard'))

        flash('Invalid email or password')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_data = mongo.users.find_one({'_id': ObjectId(current_user.get_id())})
    portfolio = user_data.get('portfolio', {})
    balance = user_data.get('balance', 0)
    
    portfolio_data = []
    total_portfolio_value = 0
    
    for symbol, position in portfolio.items():
        if position['shares'] > 0:  # Only show active positions
            try:
                # Try Polygon API
                resp = polygon_client.get_previous_close_agg(symbol)
                current_price = resp.close
            except Exception:
                # Fallback to Yahoo Finance
                stock = yf.Ticker(symbol)
                current_price = stock.history(period="1d")['Close'].iloc[-1]

            market_value = position['shares'] * current_price
            total_portfolio_value += market_value
            
            portfolio_data.append({
                'symbol': symbol,
                'shares': position['shares'],
                'avg_price': position['avg_price'],
                'current_price': current_price,
                'market_value': market_value,
                'profit_loss': market_value - (position['shares'] * position['avg_price']),
                'profit_loss_percent': ((current_price - position['avg_price']) / position['avg_price']) * 100
            })
    
    total_value = balance + total_portfolio_value
    net_profit = total_value - 10000  # Initial balance was 10k
    
    return render_template(
        'dashboard.html',
        portfolio=portfolio_data,
        balance=balance,
        total_value=total_value,
        net_profit=net_profit,
        net_profit_percent=(net_profit / 10000) * 100,
        last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/get_stock_info/<symbol>')
@login_required
def get_stock_info(symbol):
    symbol = symbol.upper()
    try:
        # Try fetching data from Polygon
        resp = polygon_client.get_previous_close_agg(symbol)
        price = resp.close
    except Exception as polygon_error:
        # If Polygon fails, fallback to Yahoo Finance
        try:
            stock = yf.Ticker(symbol)
            price = stock.history(period="1d")['Close'].iloc[-1]  # Get the last close price
        except Exception as yf_error:
            # If both fail, return an error
            return jsonify({
                'success': False,
                'error': f"Polygon error: {polygon_error}, Yahoo Finance error: {yf_error}"
            })

    return jsonify({
        'success': True,
        'price': price,
        'symbol': symbol
    })


@app.route('/buy_stock', methods=['POST'])
@login_required
def buy_stock():
    data = request.json
    symbol = data['symbol'].upper()
    shares = float(data['shares'])
    price = float(data['price'])
    reason = data['reason']
    total_cost = shares * price

    user_data = mongo.users.find_one({'_id': ObjectId(current_user.get_id())})
    current_balance = user_data['balance']
    
    if total_cost > current_balance:
        return jsonify({'success': False, 'error': 'Insufficient funds'})

    portfolio = user_data.get('portfolio', {})
    current_position = portfolio.get(symbol, {'shares': 0, 'avg_price': 0})
    
    # Calculate new average price
    total_shares = current_position['shares'] + shares
    new_avg_price = ((current_position['shares'] * current_position['avg_price']) + (shares * price)) / total_shares

    # Update portfolio and balance
    mongo.users.update_one(
        {'_id': ObjectId(current_user.get_id())},
        {
            '$set': {
                f'portfolio.{symbol}': {
                    'shares': total_shares,
                    'avg_price': new_avg_price
                },
                'balance': current_balance - total_cost
            },
            '$push': {
                'trade_history': {
                    'type': 'buy',
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'total': total_cost,
                    'reason': reason,
                    'timestamp': datetime.now()
                }
            }
        }
    )

    return jsonify({'success': True, 'new_balance': current_balance - total_cost})

@app.route('/sell_stock', methods=['POST'])
@login_required
def sell_stock():
    data = request.json
    symbol = data['symbol'].upper()
    shares = float(data['shares'])
    price = float(data['price'])
    total_value = shares * price

    user_data = mongo.users.find_one({'_id': ObjectId(current_user.get_id())})
    portfolio = user_data.get('portfolio', {})
    
    if symbol not in portfolio or portfolio[symbol]['shares'] < shares:
        return jsonify({'success': False, 'error': 'Insufficient shares'})

    current_shares = portfolio[symbol]['shares']
    new_shares = current_shares - shares
    
    update_data = {
        'balance': user_data['balance'] + total_value,
    }

    if new_shares > 0:
        update_data[f'portfolio.{symbol}.shares'] = new_shares
    else:
        update_data[f'portfolio.{symbol}'] = None

    mongo.users.update_one(
        {'_id': ObjectId(current_user.get_id())},
        {
            '$set': update_data,
            '$push': {
                'trade_history': {
                    'type': 'sell',
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'total': total_value,
                    'timestamp': datetime.now()
                }
            }
        }
    )

    return jsonify({'success': True, 'new_balance': user_data['balance'] + total_value})

# Run App
if __name__ == '__main__':
    app.run(debug=True)
