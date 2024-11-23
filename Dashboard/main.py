from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from polygon import RESTClient

# Flask App Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key

# MongoDB Setup
uri = "mongodb+srv://Ethan:L0U3pJNymy9nP1Hr@stockdash.s9jnm.mongodb.net/?retryWrites=true&w=majority&appName=StockDash"
client = MongoClient(uri, server_api=ServerApi('1'))
mongo = client['StockDash']

    
# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Polygon API Setup
polygon_client = RESTClient('rfyFIj2sCGjr8RhHOU5zgS6Hb7lTGl2p')  # Replace with your API key


# User Class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data

    def get_id(self):
        return str(self.user_data['_id'])


# User Loader for Flask-Login
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

        # Check if user already exists
        if mongo.users.find_one({'email': email}):
            flash('Email already exists')
            return redirect(url_for('register'))

        # Hash password and store user
        hashed_password = generate_password_hash(password)
        mongo.users.insert_one({
            'email': email,
            'password': hashed_password,
            'stocks': []
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
    user_stocks = current_user.user_data.get('stocks', [])
    stock_data = []

    # Fetch stock data for user's watchlist
    for symbol in user_stocks:
        try:
            resp = polygon_client.get_previous_close_agg(symbol)
            stock_data.append({
                'symbol': symbol,
                'close': resp.close,
                'high': resp.high,
                'low': resp.low
            })
        except Exception:
            flash(f'Error fetching data for {symbol}')

    return render_template('dashboard.html', stocks=stock_data)


@app.route('/add_stock', methods=['POST'])
@login_required
def add_stock():
    symbol = request.form['symbol'].upper()

    # Verify stock exists
    try:
        polygon_client.get_previous_close_agg(symbol)
    except:
        flash('Invalid stock symbol')
        return redirect(url_for('dashboard'))

    # Add stock to watchlist if not present
    if symbol not in current_user.user_data.get('stocks', []):
        mongo.users.update_one(
            {'_id': ObjectId(current_user.get_id())},
            {'$push': {'stocks': symbol}}
        )
        flash(f'Added {symbol} to your watchlist')
    else:
        flash('Stock already in watchlist')

    return redirect(url_for('dashboard'))


@app.route('/remove_stock', methods=['POST'])
@login_required
def remove_stock():
    symbol = request.form['symbol']

    # Remove stock from watchlist
    mongo.users.update_one(
        {'_id': ObjectId(current_user.get_id())},
        {'$pull': {'stocks': symbol}}
    )
    flash(f'Removed {symbol} from your watchlist')
    return redirect(url_for('dashboard'))


# Run App
if __name__ == '__main__':
    app.run(debug=True)
