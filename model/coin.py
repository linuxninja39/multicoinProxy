
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class Coin(Base):
    __tablename__ = 'Coin'

    id = Column(Integer, primary_key=True)
    name = Column(String(150))
    symbol = Column(String(3))

    def __init__(self, name=None, symbol=None):
        self.name = name
        self.symbol = symbol

    def __repr__(self):
        return "<%s('%s','%s')>" % (self.__tablename__, self.name, self.symbol)
