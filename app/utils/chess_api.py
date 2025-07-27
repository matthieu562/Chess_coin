import pandas as pd
import pytz
from datetime import datetime, timezone

from chessdotcom import get_player_stats, Client, get_player_game_archives, get_player_games_by_month


def _init_chesscom_request():
    Client.request_config['headers']['User-Agent'] = 'my-app'


def get_current_elo(chess_com_tag):
    _init_chesscom_request()

    stats = get_player_stats(chess_com_tag).json
    elo_rapid = stats['stats']['chess_rapid']['last']['rating']
    # elo_rapid = 1000
    return elo_rapid


def get_elo_df(chess_com_tag):
    _init_chesscom_request()

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
    return df


# def get_elo_rapid():
#     df = get_elo_df()
#     return df.iloc[-1]["ELO"]
