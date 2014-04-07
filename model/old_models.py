__author__ = 'melnichevv'

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref

Base = declarative_base()

class User(Base):
    __tablename__ = 'User'

    id = Column(Integer, primary_key=True)
    username = Column(name='username', type_=String(250), unique=True)
    password = Column(name='password', type_=String(250))
    remote_username = Column(name='remote_username', type_=String(250), unique=True)
    remote_password = Column(name='remote_password', type_=String(250))
    coins = relationship("UserCoin", backref='user')

    def __repr__(self):
        return "<%s('%s', '%s', '%s')>" % (self.__tablename__, self.id, self.email, self.password)

class Coin(Base):
    __tablename__ = 'Coin'

    id = Column(Integer, primary_key=True)
    name = Column(name='coin', type_=String(150), unique=True)
    symbol = Column(name='symbol', type_=String(150), unique=True)
    users = relationship("UserCoin", backref = 'coin')

    def __init__(self, name=None, symbol=None):
        self.name = name
        self.symbol = symbol

    def __repr__(self):
        return "<%s('%s','%s')>" % (self.__tablename__, self.name, self.symbol)

class UserCoin(Base):
    __tablename__ = 'UserCoin'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("User.id"))
    coin_id = Column(Integer, ForeignKey("Coin.id"))
    # coin = relationship("Coin")

    # user = relationship('User', backref=backref('UserCoin'))

    # def __init__(self, userId=None, coinId=None):
    #     self.userId = userId
    #     self.coinId = coinId

    def __repr__(self):
        return "<%s('%s','%s')>" % (self.__tablename__, self.user_id, self.coin_id)
