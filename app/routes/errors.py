from flask import Blueprint, render_template, session

from app.utils.chess_api import get_current_elo
from config import CHESS_MAPPING, LOIC_USERNAME


errors = Blueprint('errors', __name__)


@errors.app_errorhandler(404)
def page_not_found(e):
    return render_template(
        template_name_or_list='404.html',
        username=session.get('username'),
        elo_rapid=session.get(
            'selected_chess_com_tag_value',
            get_current_elo(
                session.get('selected_chess_com_tag', LOIC_USERNAME)
            )
        ),
        assets=list(CHESS_MAPPING.keys())
    ), 404
