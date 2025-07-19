import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from flask import Flask, render_template_string, session, request, redirect, url_for, render_template
from chessdotcom import get_player_stats, Client
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

#for test
import plotly
import plotly.express as px
import pandas as pd
import json


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

SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
SECRET_KEY = os.environ.get("SECRET_KEY")

app = Flask(__name__)
app.secret_key = SECRET_KEY
print(SQLALCHEMY_DATABASE_URI)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

db = SQLAlchemy(app)


class EloHistory(db.Model):
    __tablename__ = 'elo_history'
    id = db.Column(db.Integer, primary_key=True)
    chess_com_tag = db.Column(db.String(80), nullable=False, default="Lo_Chx")
    asset = db.Column(db.String(80), nullable=False, default="Loïc_coin")
    elo = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    @staticmethod
    def get_current_elo(asset): # Pour gérer les positions sans mettre forcément dans le graphic
        Client.request_config['headers']['User-Agent'] = 'my-app'
        chess_com_tag = EloHistory.query.filter_by(asset=asset).first().chess_com_tag
        stats = get_player_stats(chess_com_tag).json
        elo_rapid = stats['stats']['chess_rapid']['last']['rating']
        # elo_rapid = 500
        return elo_rapid

    @staticmethod
    def update_assets():
        assets = EloHistory.get_all_assets_name()
        
        for asset in assets:
            current_elo = EloHistory.get_current_elo(asset)
            
            latest_elo_entry = db.session.query(EloHistory).filter_by(asset=asset).order_by(EloHistory.timestamp.desc()).first()
            if latest_elo_entry:
                latest_timestamp = latest_elo_entry.timestamp
                if latest_timestamp.tzinfo is None:
                    latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)  # Ajouter le fuseau horaire UTC si nécessaire
                time_difference = datetime.now(timezone.utc) - latest_timestamp
                if time_difference < timedelta(hours=6):
                    latest_elo_entry.elo = current_elo
                    latest_elo_entry.timestamp = datetime.now(timezone.utc)
                    db.session.commit()
                else:
                    new_entry = EloHistory(elo=current_elo, asset=asset, timestamp=datetime.now(timezone.utc))
                    db.session.add(new_entry)
                    db.session.commit()
            else:
                new_entry = EloHistory(elo=current_elo, asset=asset, timestamp=datetime.now(timezone.utc))
                db.session.add(new_entry)
                db.session.commit()
    
    @staticmethod
    def get_all_assets_name():
        assets = db.session.query(EloHistory.asset).distinct().all() # Récupérer tous les noms des assets une fois
        assets = [a[0] for a in assets]  # extraire les noms depuis les tuples
        return assets

class Position(db.Model):
    __tablename__ = 'positions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # positive = long, negative = short
    entry_price = db.Column(db.Float, nullable=False)
    #timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    user = db.relationship('User', back_populates='open_positions')

    def get_position_value(self):
        current_elo = EloHistory.get_current_elo(self.asset)
        position_value = abs(self.quantity) * current_elo
        print(f"Position value: {position_value}")
        return position_value

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

    def open_position(self):
        asset = request.form['asset']
        latest_elo = EloHistory.query.filter_by(asset=asset).order_by(EloHistory.timestamp.desc()).first()
        # Check 'quantity' -> allowed value ? : not 0?, not too much value than available_funds permits?, is a float? 
        try:
            quantity = float(request.form['quantity']) 
            if quantity == 0:
                raise ValueError("Quantity can't be zero")
            if self is None:
                raise ValueError("User not found")
            max_quantity = self.available_funds / latest_elo.elo
            if abs(quantity) > max_quantity:
                raise ValueError("Not enough funds")
        except (ValueError, TypeError) as e:
            return f"Invalid quantity: {e} <br><a href='/trade'>Back</a>"
        
        self.available_funds -= abs(quantity) * latest_elo.elo
        new_position = Position(user_id=self.id, asset=asset, quantity=quantity, entry_price=latest_elo.elo)
        db.session.add(new_position)
        db.session.commit()

        # Save data temporary
        # session['last_order'] = {
        #     'asset': asset,
        #     'quantity': quantity
        # }

        return 0

    def close_position(self, position_id):
        position = Position.query.filter_by(id=position_id, user_id=self.id).first()
        self.available_funds += position.get_position_value()

        db.session.delete(position)
        db.session.commit()

    def get_equity(self):
        positions = Position.query.filter_by(user_id=self.id)

        position_values = 0
        for position in positions:
            position_values += position.get_position_value()

        return self.available_funds + position_values

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

with app.app_context():
    # db.drop_all()
    db.create_all()

# @app.route('/update', methods=['GET'])
# def update_db():
#     EloHistory.update_assets()
#     return "end"

# @app.route('/eq', methods=['GET'])
# def eq():
#     user = User.query.filter_by(username=session['username']).first()
#     print("User funds :", user.available_funds, "User equity :", user.get_equity())
#     return "end"

@app.route('/leaderboard')
def leaderboard():
    # Récupérer tous les users
    users = User.query.all()

    leaderboard_data = []
    for user in users:
        equity = user.get_equity()

        # Chercher la quantité de Loïc_coin dans ses positions ouvertes
        loic_coin_qty = 0
        for pos in user.open_positions:
            if pos.asset == 'Loïc_coin':
                loic_coin_qty += pos.quantity

        leaderboard_data.append({
            'username': user.username,
            'equity': equity,
            'loic_coin_qty': loic_coin_qty
        })

    # Trier par equity décroissante et prendre les 10 premiers
    leaderboard_data = sorted(leaderboard_data, key=lambda x: x['equity'], reverse=True)[:10]

    return render_template('leaderboard.html', leaderboard=leaderboard_data)

@app.route('/trade', methods=['GET', 'POST'])
def trade():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()

    # When accessing the page, always update the value in the table :
    EloHistory.update_assets()

    # Actualiser les valeurs si demandé par ?update=1
    if request.method == 'GET' and request.args.get('update') == '1':
        EloHistory.update_assets()

    assets = EloHistory.get_all_assets_name()

    # Construire la liste assets_values avec valeur actuelle
    assets_values = []
    for asset in assets:
        latest_elo_entry = EloHistory.query.filter_by(asset=asset).order_by(EloHistory.timestamp.desc()).first()
        value = latest_elo_entry.elo if latest_elo_entry else 0
        assets_values.append({'asset': asset, 'value': value})

    if request.method == 'POST':
        if request.form.get('open_position') == '1':
            error = user.open_position()
            if error:
                return error
            else:
                #last_order = session.get('last_order', None)
                return redirect(url_for('trade'))  # recharger proprement
        if request.form.get('close_position') == '1':
            position_id = request.form.get('position_id')
            user.close_position(position_id)
            return redirect(url_for('trade'))


    # Préparer les positions
    positions = []
    for pos in user.open_positions:
        latest_elo_entry = EloHistory.query.filter_by(asset=pos.asset).order_by(EloHistory.timestamp.desc()).first()
        current_elo = latest_elo_entry.elo if latest_elo_entry else 0
        position_value = abs(pos.quantity) * current_elo
        positions.append({
            'id': pos.id,
            'asset': pos.asset,
            'quantity': pos.quantity,
            'entry_price': pos.entry_price,
            'position_value': position_value
        })

    available_funds = user.available_funds

    return render_template('trade_and_positions.html',
                           assets=assets,
                           assets_values=assets_values,
                           positions=positions,
                           available_funds=available_funds)

# Ne foncitonne pas
@app.route('/force/<int:value>', methods=['GET'])
def force_value(value):
    """Force un nouvel ELO pour un asset donné"""
    new_entry = EloHistory(asset="Loïc_coin", elo=value)
    db.session.add(new_entry)
    db.session.commit()
    return redirect(url_for('trade'))

@app.route('/elo')
def show_latest_elo():
    # Récupération de toutes les entrées ELO
    all_elo_entries = EloHistory.query.order_by(EloHistory.timestamp.asc()).all()

    if not all_elo_entries:
        return "Aucune donnée ELO en base. <a href='/force/Loïc_coin/1000'>Ajouter une valeur</a>"

    # Préparer les données dans un DataFrame
    data = [{
        'timestamp': entry.timestamp,
        'elo': entry.elo,
        'asset': entry.asset
    } for entry in all_elo_entries]

    df = pd.DataFrame(data)

    # Tracer un graphique avec une courbe par asset
    fig = px.line(df, x='timestamp', y='elo', color='asset', title='History of ELO values over time')
    elo_graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    loic_latest = next((entry for entry in reversed(all_elo_entries) if entry.asset == "Loïc_coin"), None)
    elo_rapid = loic_latest.elo if loic_latest else None

    username = session.get('username')
    return render_template('home.html', elo_rapid=elo_rapid, loic_coin_graph=elo_graph, username=username)

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
