from flask import Flask, render_template_string, session, request, redirect, url_for
from chessdotcom import get_player_stats, Client
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timezone

LOCAL = True

app = Flask(__name__)
if LOCAL:
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres@localhost:5432/test_db"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
db = SQLAlchemy(app)

app.secret_key = b'_5#y2L"F4ZQ8z\n\xec]/'

class EloHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    elo = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

with app.app_context():
    db.create_all()

@app.route('/update', methods=['POST'])
def fetch_and_save_elo(username="Lo_Chx"):
    Client.request_config['headers']['User-Agent'] = 'my-app'
    stats = get_player_stats(username).json
    elo_rapid = stats['stats']['chess_rapid']['last']['rating']
    new_entry = EloHistory(username=username, elo=elo_rapid)
    db.session.add(new_entry)
    db.session.commit()
    return f"ELO mis à jour : {elo_rapid} <br><a href='/'>Retour</a>"

@app.route('/elo')
def show_latest_elo():
    latest = EloHistory.query.order_by(EloHistory.timestamp.desc()).first()
    if not latest:
        elo = fetch_and_save_elo()
        return f"Pas de données précédentes. Elo récupéré et stocké : {elo}"
    return  render_template_string('''
        <h1>Dernier ELO</h1>
        <p>{{ username }} : {{ elo }} ({{ timestamp }})</p>
        <form action="/update" method="post">
            <button type="submit">Mettre à jour l'ELO</button>
        </form>
    ''', username=latest.username, elo=latest.elo, timestamp=latest.timestamp)

@app.route('/')
def index():
    if 'username' in session:
        return f'''
            Connecté en tant que {session["username"]} <br>
            <a href="/elo">Voir ELO</a><br>
            <a href="/logout">Logout</a>
        '''
    return '''
        Vous n'êtes pas connecté.<br>
        <a href="/login"><button>Se connecter</button></a>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect(url_for('index'))
    return '''
        <form method="post">
            <p><input type=text name=username>
            <p><input type=submit value=Login>
        </form>
    '''

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run()


