from flask import Blueprint, render_template, session

from app.models import User
from app.utils.chess_api import get_current_elo
from config import LOIC_USERNAME


leaderboard = Blueprint('leaderboard', __name__)


@leaderboard.route('/leaderboard')
def leaderboard_page():
    users = User.query.all()

    leaderboard_data = []
    for user in users:
        equity = user.get_equity()
        loic_coin_qty = sum(pos.quantity for pos in user.open_positions if pos.asset == 'Loïc_coin')

        leaderboard_data.append({
            'username': user.username,
            'equity': equity,
            'loic_coin_qty': loic_coin_qty
        })

    # Tri + classement
    leaderboard_data.sort(key=lambda x: x['equity'], reverse=True)
    current_rank = 1
    ranked = []
    for i, player in enumerate(leaderboard_data):
        player['rank'] = ranked[-1]['rank'] if i > 0 and player['equity'] == ranked[-1]['equity'] else current_rank
        ranked.append(player)
        current_rank += 1

    return render_template(
        template_name_or_list='leaderboard.html',
        username=session.get('username'),
        elo_rapid=get_current_elo(session.get('selected_chess_com_tag', LOIC_USERNAME)),
        leaderboard=ranked
    )
