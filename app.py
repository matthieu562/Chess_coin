import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from flask import Flask, render_template_string, session, request, redirect, url_for, render_template
from chessdotcom import get_player_stats, Client
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

#for test
import plotly
import plotly.express as px
import pandas as pd
import json

DB_NAME = "test_db"
DB_USER = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"

"""
def create_db_if_not_exists():
    conn = psycopg2.connect(dbname='postgres', user=DB_USER, host=DB_HOST, port=DB_PORT)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
    exists = cur.fetchone()
    if not exists:
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
    cur.close()
    conn.close()

create_db_if_not_exists()
"""

LOCAL = False

app = Flask(__name__)
if LOCAL:
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
db = SQLAlchemy(app)

app.secret_key = b'_5#y2L"F4ZQ8z\n\xec]/'

class EloHistory(db.Model):
    __tablename__ = 'elo_history'
    id = db.Column(db.Integer, primary_key=True)
    chess_com_tag = db.Column(db.String(80), nullable=False, default="Lo_Chx")
    asset = db.Column(db.String(80), nullable=False, default="Loïc_coin")
    elo = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

class Position(db.Model):
    __tablename__ = 'positions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # positive = long, negative = short
    entry_price = db.Column(db.Float, nullable=False)
    #timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    user = db.relationship('User', back_populates='open_positions')

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # mail for password recupération
    available_funds = db.Column(db.Integer, nullable=False)
    open_positions = db.relationship('Position', back_populates='user', cascade='all, delete-orphan')
    password_hash = db.Column(db.String(512), nullable=False)
    #open_positions  = # list of open positions
    #position : [asset, entry price, position size (capital_at_risk), direction (long/short) pas necessaire si c le 
    #   signe de position size, le timestamp?]
    #not needed : portfolio_value = available_funds + get_profit(open_positions)
    #accéder à toutes les positions ouvertes d’un user avec :
    #   user.open_positions

    #get_equity()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

with app.app_context():
    #db.drop_all()
    db.create_all()

@app.route('/update', methods=['POST'])
def fetch_and_save_elo(chess_com_tag="Lo_Chx"):
    # all assets should be updated here
    Client.request_config['headers']['User-Agent'] = 'my-app'
    stats = get_player_stats(chess_com_tag).json
    elo_rapid = stats['stats']['chess_rapid']['last']['rating']
    # elo_rapid = 487
    new_entry = EloHistory(elo=elo_rapid)
    db.session.add(new_entry)
    db.session.commit()
    return f"ELO updated: {elo_rapid} <br><a href='/'>Back</a>"

@app.route('/test', methods=['GET', 'POST'])
def test():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()

    assets = db.session.query(EloHistory.asset).distinct().all()
    assets = [a[0] for a in assets]  # extraire les noms depuis les tuples

    if request.method == 'POST':
        asset = request.form['asset']
        latest_elo = EloHistory.query.filter_by(asset=asset).order_by(EloHistory.timestamp.desc()).first()
        # Check 'quantity' -> allowed value ? : not 0?, not too much value than available_funds permits?, is a float? 
        try:
            quantity = float(request.form['quantity']) 
            if quantity == 0:
                raise ValueError("Quantity can't be zero")
            if user is None:
                raise ValueError("User not found")
            max_quantity = user.available_funds / latest_elo.elo
            if abs(quantity) > max_quantity:
                raise ValueError("Not enough funds")
        except (ValueError, TypeError) as e:
            return f"Invalid quantity: {e} <br><a href='/test'>Back</a>"

        
        user.available_funds -= abs(quantity) * latest_elo.elo
        new_position = Position(user_id=user.id, asset=asset, quantity=quantity, entry_price=latest_elo.elo)
        db.session.add(new_position)
        db.session.commit()

        return f"Position opened: {quantity} {asset} <br><a href='/'>Back</a>" # Préciser le prix courant et le montant total ?

    return render_template_string('''
        <h2>Open a Position</h2>
        <form method="post">
            <label for="asset">Choose an asset:</label><br>
            <select name="asset" required>
                {% for asset in assets %}
                    <option value="{{ asset }}">{{ asset }}</option>
                {% endfor %}
            </select><br><br>
            <input type="number" step="any" name="quantity" placeholder="Quantity (e.g. 1.5)" required><br>
            <input type="submit" value="Open Position">
        </form>
        <br><a href="/">Back</a>
    ''', assets=assets)

@app.route('/elo')
def show_latest_elo():
    latest = EloHistory.query.order_by(EloHistory.timestamp.desc()).first()
    if not latest:
        fetch_and_save_elo()
        return render_template('home.html', elo_rapid=latest.elo, username=session["username"], loic_coin_graph=loic_coin_graph)

    df = pd.DataFrame({
        "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
        "Amount": [4, 1, 2, 2, 4, 5],
        "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"]
    })
    fig = px.bar(df, x="Fruit", y ="Amount", color ="City", barmode ="group")
    loic_coin_graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    username = session.get('username')
    return render_template('home.html', elo_rapid=latest.elo, username=username, loic_coin_graph=loic_coin_graph)
    # return render_template_string('''
    #     <h1>Latest ELO</h1>
    #     <p>{{ username }} : {{ elo }} ({{ timestamp }})</p>
    #     <form action="/update" method="post">
    #         <button type="submit">Update ELO</button>
    #     </form>
    # ''', username=latest.username, elo=latest.elo, timestamp=latest.timestamp)

@app.route('/')
def home():
    return redirect(url_for('show_latest_elo'))
    # if 'username' in session:
    #     return f'''
    #         Logged in as {session["username"]} <br>
    #         <a href="/elo">View ELO</a><br>
    #         <a href="/logout">Logout</a>
    #     '''
    # return '''
    #     You are not logged in.<br>
    #     <a href="/login"><button>Log in</button></a>
    #     <a href="/register"><button>Sign up</button></a>
    # '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session['username'] = user.username
            return redirect(url_for('home'))
        return 'Incorrect username or password.'
    return render_template(
        'login.html'
    )
    # return render_template_string('''
    #     <h2>Login</h2>
    #     <form method="post">
    #         <p><input type="text" name="username" placeholder="Username" required></p>
    #         <p><input type="password" name="password" placeholder="Password" required></p>
    #         <p><input type="submit" value="Log in"></p>
    #     </form>
    #     <p><a href="/register">No account? Sign up</a></p>
    # ''')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return 'Username already taken.'
        new_user = User(username=username, available_funds=1000) 
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        return redirect(url_for('home'))
    return render_template(
        'register.html'
    )
    # return render_template_string('''
    #     <h2>Create an account</h2>
    #     <form method="post">
    #         <p><input type="text" name="username" placeholder="Username" required></p>
    #         <p><input type="password" name="password" placeholder="Password" required></p>
    #         <p><input type="submit" value="Sign up"></p>
    #     </form>
    #     <p><a href="/login">Already have an account? Log in</a></p>
    # ''')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
