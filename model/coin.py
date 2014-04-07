from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref

Base = declarative_base()

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
