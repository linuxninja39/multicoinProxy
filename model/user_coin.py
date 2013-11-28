
from sqlalchemy import Column, Integer, String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

from model.user import User

Base = declarative_base()

class UserCoin(Base):
	__tablename__ = 'UserCoin'

	id = Column(Integer, primary_key=True)
	userId = Column(Integer)
	coinId = Column(Integer)

	user = relationship('User', backref=backref('UserCoin'))

	def __init__(self, userId=None, coinId=None):
		self.userId = userId
		self.coinId = coinId

	def __repr__(self):
		return "<%s('%s','%s')>" % (self.__tablename__, self.userId, self.coinId)
