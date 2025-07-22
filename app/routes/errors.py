from flask import Blueprint, render_template, session

from app.utils.chess_api import get_elo_rapid


errors = Blueprint('errors', __name__)


@errors.app_errorhandler(404)
def page_not_found(e):
    return render_template(
        template_name_or_list='404.html',
        username=session.get('username'),
        elo_rapid=get_elo_rapid()
    ), 404