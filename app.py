
from flask import Flask

app = Flask(__name__)
from chessdotcom import get_player_stats, Client


app = Flask(__name__)
@app.route('/')
def hello():
    return 'Hello, World!'

    # Définir un User-Agent valide
    Client.request_config['headers']['User-Agent'] = 'toto'

    stats = get_player_stats("Lo_Chx").json
    elo_rapid = stats['stats']['chess_rapid']['last']['rating']
    #print("Elo rapid :", elo_rapid)
    return f"Le ELO de Loïc est de {elo_rapid}"

print(hello())
