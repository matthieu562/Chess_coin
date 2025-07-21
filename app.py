from flask import Flask, session, request, redirect, url_for, render_template, render_template_string
from chessdotcom import get_player_stats, Client, get_player_game_archives, get_player_games_by_month
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import timezone
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

import pytz
import pandas as pd
import json
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import HoverTool, Legend
from bokeh.resources import CDN

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
# SQLALCHEMY_DATABASE_URI = "postgresql://postgres@localhost:5432/test_db"
# SECRET_KEY =  "5#y2LF4ZQ8&sefc7"
app = Flask(__name__)
app.secret_key = SECRET_KEY
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
        if(self.quantity > 0):
            position_value = (current_elo / self.entry_price) * (self.quantity * self.entry_price)
        elif(self.quantity < 0):
            position_value = (self.entry_price / current_elo) * (-self.quantity * self.entry_price)
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

    # Trier par equity décroissante
    leaderboard_data = sorted(leaderboard_data, key=lambda x: x['equity'], reverse=True)

    # Ajouter le classement avec gestion des égalités
    ranked_leaderboard = []
    current_rank = 1
    for index, player in enumerate(leaderboard_data):
        if index > 0 and player['equity'] == leaderboard_data[index - 1]['equity']:
            player['rank'] = ranked_leaderboard[-1]['rank']  # même rang que précédent
        else:
            player['rank'] = current_rank

        ranked_leaderboard.append(player)
        current_rank += 1

    # Trier par equity décroissante et prendre les 10 premiers
    # leaderboard_data = sorted(leaderboard_data, key=lambda x: x['equity'], reverse=True)[:10]

    username = session.get('username')
    elo_rapid = get_elo_rapid()

    return render_template('leaderboard.html', username=username, elo_rapid=elo_rapid, leaderboard=ranked_leaderboard)

@app.route('/give', methods=['GET', 'POST'])
def give():
    user = User.query.filter_by(username=session['username']).first()
    user.available_funds += 500
    db.session.commit()
    return render_template_string('ok')

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


@app.errorhandler(404)
def page_not_found(e):


    username = session.get('username')
    elo_rapid = get_elo_rapid()

    return render_template('404.html', username=username, elo_rapid=elo_rapid)

# Ne fonctionne pas
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
    # all_elo_entries = EloHistory.query.order_by(EloHistory.timestamp.asc()).all()

    # if not all_elo_entries:
    #     return "Aucune donnée ELO en base. <a href='/force/Loïc_coin/1000'>Ajouter une valeur</a>"

    # Préparer les données dans un DataFrame
    Client.request_config['headers']['User-Agent'] = 'my-app'
    chess_com_tag = "Lo_Chx"
    games_info = get_player_game_archives(chess_com_tag).json

    local_tz = pytz.timezone("Europe/Paris")

    elo_evolution = []
    for archive_url in games_info['archives']:

        parts = archive_url.strip("/").split("/")
        if len(parts) < 2:
            print(f"Archive URL invalide : {archive_url}")
            continue

        year, month = parts[-2], parts[-1]
        month_games = get_player_games_by_month(chess_com_tag, year, month).json['games']

        for game in month_games:
            if game["rules"] != "chess" or game["time_class"] != "rapid":
                continue
            ts_utc = datetime.fromtimestamp(game.get("end_time", 0), tz=timezone.utc)
            ts_local = ts_utc.astimezone(local_tz)
            if chess_com_tag.lower() in game["white"]["username"].lower():
                rating = game["white"]["rating"]
            elif chess_com_tag.lower() in game["black"]["username"].lower():
                rating = game["black"]["rating"]
            else:
                continue
            elo_evolution.append((ts_local, rating))

    # Supprimer les doublons (par timestamp), garder le plus récent
    seen = {}
    for t, r in elo_evolution:
        seen[t] = r

    df = pd.DataFrame(sorted(seen.items()), columns=["Date", "ELO"])
    df = df[1:]
    df['Date'] = pd.to_datetime(df['Date'])
    df['ELO'] = pd.to_numeric(df['ELO'], errors='coerce')
    # df["Player"] = "Loïc Coin"
    # return render_template_string(f"Df is empty: {df_clean[['Date', 'ELO']].tail(10)}")

    # data = [{
    #     'timestamp': entry.timestamp,
    #     'elo': int(entry.elo),
    #     'asset': entry.asset
    # } for entry in all_elo_entries]
    #
    # df = pd.DataFrame(data)

    # df["timestamp"] = pd.to_datetime(df["timestamp"])
    # df["elo"] = pd.to_numeric(df["elo"], errors="coerce")

    # Tracer un graphique avec une courbe par asset
    # fig = px.line(df, x="Date", y="ELO", color="Player", title="History of ELO values over time", markers=True)
    # elo_graph = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    # Création du plot Bokeh
    p = figure(x_axis_type='datetime',
               sizing_mode="stretch_width",
               height=400,
               tools="pan,wheel_zoom,box_zoom,reset,save")

    # Ligne + points
    line = p.line(df['Date'], df['ELO'], line_width=2)
    p.circle(df['Date'], df['ELO'], size=4, fill_color="black")

    # Légende personnalisée (hors zone du graphe)
    legend = Legend(items=[("Loïc Coin", [line])])
    legend.label_text_font_size = "13px"
    p.add_layout(legend, 'below')  # En dehors à droite

    # Axes labels
    p.xaxis.axis_label = 'Date'
    p.yaxis.axis_label = 'ELO'

    # Hover tooltip
    hover = HoverTool(tooltips=[("Date", "@x{%F %T}"), ("ELO", "@y")],
                      formatters={'@x': 'datetime'},
                      mode='vline')
    p.add_tools(hover)

    # Génération des scripts et div à insérer dans la page HTML
    script, div = components(p)
    cdn_js = CDN.js_files[0]
    cdn_css = CDN.css_files[0] if CDN.css_files else None

    # loic_latest = next((entry for entry in reversed(all_elo_entries) if entry.asset == "Loïc_coin"), None)
    # elo_rapid = loic_latest.elo if loic_latest else None
    elo_rapid = df.iloc[-1]["ELO"]

    username = session.get('username')
    return render_template('home.html', elo_rapid=elo_rapid, script=script, div=div, cdn_js=cdn_js, cdn_css=cdn_css, username=username)
    # return render_template('home.html', elo_rapid=elo_rapid, loic_coin_graph=elo_graph, username=username)

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
    return render_template('login.html')
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
    return render_template('register.html')
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


def get_elo_rapid():
    # Préparer les données dans un DataFrame
    Client.request_config['headers']['User-Agent'] = 'my-app'
    chess_com_tag = "Lo_Chx"
    games_info = get_player_game_archives(chess_com_tag).json

    local_tz = pytz.timezone("Europe/Paris")

    elo_evolution = []
    for archive_url in games_info['archives']:

        parts = archive_url.strip("/").split("/")
        if len(parts) < 2:
            print(f"Archive URL invalide : {archive_url}")
            continue

        year, month = parts[-2], parts[-1]
        month_games = get_player_games_by_month(chess_com_tag, year, month).json['games']

        for game in month_games:
            if game["rules"] != "chess" or game["time_class"] != "rapid":
                continue
            ts_utc = datetime.fromtimestamp(game.get("end_time", 0), tz=timezone.utc)
            ts_local = ts_utc.astimezone(local_tz)
            if chess_com_tag.lower() in game["white"]["username"].lower():
                rating = game["white"]["rating"]
            elif chess_com_tag.lower() in game["black"]["username"].lower():
                rating = game["black"]["rating"]
            else:
                continue
            elo_evolution.append((ts_local, rating))

    # Supprimer les doublons (par timestamp), garder le plus récent
    seen = {}
    for t, r in elo_evolution:
        seen[t] = r

    df = pd.DataFrame(sorted(seen.items()), columns=["Date", "ELO"])
    df = df[1:]
    df['Date'] = pd.to_datetime(df['Date'])
    df['ELO'] = pd.to_numeric(df['ELO'], errors='coerce')
    return df.iloc[-1]["ELO"]


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)


# Upgrades
# - Add a maximum number of characters for username (7) else >= ...

# BugFix
# - Erreur de valeur d'equity quand les actions montent et descendent
# - Erreur valeur de coin quand on achète et vend en même temps

# catter(size=...) instead of circle() in Bokeh