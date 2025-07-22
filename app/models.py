from datetime import datetime, timedelta, timezone

from flask import request
from werkzeug.security import generate_password_hash, check_password_hash
from chessdotcom import get_player_stats, Client

from . import db


class EloHistory(db.Model):
    __tablename__ = 'elo_history'
    id = db.Column(db.Integer, primary_key=True)
    chess_com_tag = db.Column(db.String(80), nullable=False, default="Lo_Chx")
    asset = db.Column(db.String(80), nullable=False, default="Loïc_coin")
    elo = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    @staticmethod
    def get_current_elo(asset):  # Pour gérer les positions sans mettre forcément dans le graphic
        Client.request_config['headers']['User-Agent'] = 'my-app'
        chess_com_tag = EloHistory.query.filter_by(asset=asset).first().chess_com_tag
        stats = get_player_stats(chess_com_tag).json
        elo_rapid = stats['stats']['chess_rapid']['last']['rating']
        # elo_rapid = 1000
        return elo_rapid

    @staticmethod
    def update_assets():
        assets = EloHistory.get_all_assets_name()

        for asset in assets:
            current_elo = EloHistory.get_current_elo(asset)

            latest_elo_entry = db.session.query(EloHistory).filter_by(asset=asset).order_by(
                EloHistory.timestamp.desc()).first()
            if latest_elo_entry:
                latest_timestamp = latest_elo_entry.timestamp
                if latest_timestamp.tzinfo is None:
                    latest_timestamp = latest_timestamp.replace(
                        tzinfo=timezone.utc)  # Ajouter le fuseau horaire UTC si nécessaire
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
        assets = db.session.query(EloHistory.asset).distinct().all()  # Récupérer tous les noms des assets une fois
        assets = [a[0] for a in assets]  # extraire les noms depuis les tuples
        return assets


class Position(db.Model):
    __tablename__ = 'positions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # positive = long, negative = short
    entry_price = db.Column(db.Float, nullable=False)
    # timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    user = db.relationship('User', back_populates='open_positions')

    def get_position_value(self):
        current_elo = EloHistory.get_current_elo(self.asset)
        if (self.quantity > 0):
            position_value = (current_elo / self.entry_price) * (self.quantity * self.entry_price)
        elif (self.quantity < 0):
            position_value = (self.entry_price / current_elo) * (-self.quantity * self.entry_price)
        else:
            # self.quantity cannot be equal to 0
            raise ValueError

        return position_value


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # mail for password recupération
    available_funds = db.Column(db.Integer, nullable=False)
    open_positions = db.relationship('Position', back_populates='user', cascade='all, delete-orphan')
    password_hash = db.Column(db.String(512), nullable=False)

    # open_positions  = # list of open positions
    # position : [asset, entry price, position size (capital_at_risk), direction (long/short) pas necessaire si c le
    #   signe de position size, le timestamp?]
    # not needed : portfolio_value = available_funds + get_profit(open_positions)
    # accéder à toutes les positions ouvertes d’un user avec :
    #   user.open_positions

    def open_position(self):
        asset = request.form['asset']
        latest_elo = EloHistory.query.filter_by(asset=asset).order_by(EloHistory.timestamp.desc()).first()

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
            return f"Invalid quantity: {e}"

        self.available_funds -= abs(quantity) * latest_elo.elo
        new_position = Position(user_id=self.id, asset=asset, quantity=quantity, entry_price=latest_elo.elo)
        db.session.add(new_position)
        db.session.commit()
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