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
