from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from app import db
from app.models import User, EloHistory
from app.utils.chess_api import get_current_elo
from config import CHESS_MAPPING, LOIC_USERNAME

trade = Blueprint('trade', __name__)


@trade.route('/trade', methods=['GET', 'POST'])
def trading_page():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(username=session['username']).first() # SaNsE
    EloHistory.update_assets()

    # assets = EloHistory.get_all_assets_name()
    assets = list(CHESS_MAPPING.keys())
    selected_asset = session.get('selected_asset', 'Loïc_Coin')

    # We want to put selected_asset in first position
    if selected_asset in assets:
        assets.remove(selected_asset)
    assets.insert(0, selected_asset)

    if request.method == 'POST':
        if request.form.get('open_position') == '1':
            try:
                quantity = float(request.form.get('quantity'))
                if quantity == 0:
                    flash("Quantity cannot be zero.", "danger")
                    return redirect(url_for('trade.trading_page'))
            except ValueError:
                flash("Invalid quantity format.", "danger")
                return redirect(url_for('trade.trading_page'))

            error = user.open_position()
            flash("Position opened!" if not error else error, "success" if not error else "danger")
            return redirect(url_for('trade.trading_page'))

        if request.form.get('close_position') == '1':
            user.close_position(request.form.get('position_id'))
            return redirect(url_for('trade.trading_page'))

    positions = [
        {
        'id': pos.id,
        'asset': pos.asset,
        'quantity': pos.quantity,
        'entry_price': pos.entry_price,
        'position_value': pos.get_position_value()
        }
        for pos in user.open_positions
    ]

    return render_template(
        template_name_or_list='trade.html',
        username=user.username,
        elo_rapid=session.get(
            'selected_chess_com_tag_value',
            get_current_elo(
                session.get('selected_chess_com_tag', LOIC_USERNAME)
            )
        ),
        assets=assets,
        positions=positions,
        available_funds=user.available_funds
    )


@trade.route('/force/<int:value>')
def force_value(value):
    """Force un nouvel ELO pour un asset donné"""
    new_entry = EloHistory(asset="Loïc_coin", elo=value)
    db.session.add(new_entry)
    db.session.commit()
    return redirect(url_for('trade.trading_page'))


@trade.route('/give', methods=['GET', 'POST'])
def give():
    user = User.query.filter_by(username=session['username']).first()
    user.available_funds += 500
    db.session.commit()
    return render_template('OK - 500 coins added')

@trade.route('/update_selected_asset', methods=['POST'])
def update_selected_asset():
    data = request.get_json()
    selected_asset = data.get('asset')

    if not selected_asset:
        return jsonify({'status': 'error', 'message': 'No asset provided'}), 400

    session['selected_asset'] = selected_asset
    session['selected_chess_com_tag'] = CHESS_MAPPING[selected_asset]
    new_elo = get_current_elo(session.get('selected_chess_com_tag'))
    session['selected_chess_com_tag_value'] = new_elo
    return jsonify({'status': 'ok', 'selected': selected_asset, 'elo_rapid': new_elo})
