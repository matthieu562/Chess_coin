import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default_key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


LOIC_USERNAME = 'Lo_Chx'

CHESS_MAPPING = {
    'Loïc_Coin': 'Lo_Chx',
    'Matt_Coin': 'matt292',
    'Quentin_Coin': 'Ciudalcampo2',
    'Test_Coin': 'Ciudal'
}
