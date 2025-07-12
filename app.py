

from flask import Flask, render_template
from chessdotcom import get_player_stats, Client
from flask_sqlalchemy import SQLAlchemy
import os

from sqlalchemy.orm import Mapped, mapped_column


database_url = os.environ.get("DATABASE_URL")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
db = SQLAlchemy(app)

class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str]

with app.app_context():
    db.create_all()

new_user = User(username="Matt")
db.session.add(new_user)
db.session.commit()


@app.route('/')
def hello():
    # Définir un User-Agent valide
    Client.request_config['headers']['User-Agent'] = 'toto'

    stats = get_player_stats("Lo_Chx").json
    elo_rapid = stats['stats']['chess_rapid']['last']['rating']
    #print("Elo rapid :", elo_rapid)
    # return f"Le ELO de Loïc est de {elo_rapid}"
    return render_template('test.html', elo_rapid=elo_rapid)


"""
from flask import Flask, render_template
from chessdotcom import get_player_stats, Client
from flask_sqlalchemy import SQLAlchemy
import os

# Initialisation de l'app Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
db = SQLAlchemy(app)

# Modèle de base de données
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

# Initialisation de la DB (exécuter une fois, pas à chaque démarrage)
@app.before_first_request
def create_tables():
    db.create_all()
    if not User.query.filter_by(username="Matt").first():
        new_user = User(username="Matt")
        db.session.add(new_user)
        db.session.commit()

# Route principale
@app.route('/')
def hello():
    Client.request_config['headers']['User-Agent'] = 'toto'
    stats = get_player_stats("Lo_Chx").json
    elo_rapid = stats['stats']['chess_rapid']['last']['rating']
    return render_template('test.html', elo_rapid=elo_rapid)
"""