from .auth import auth
from .errors import errors
from .home import home
from .trade import trade
from .leaderboard import leaderboard

def register_routes(app):
    app.register_blueprint(auth)
    app.register_blueprint(errors)
    app.register_blueprint(home)
    app.register_blueprint(trade)
    app.register_blueprint(leaderboard)
