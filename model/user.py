
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class User(Base):
    __tablename__ = 'User'

    id = Column(Integer, primary_key=True)
    email = Column(String(250))
    password = Column(String(250))

    def __init__(self, email=None, password=None):
        self.email = email
        self.password = password

    def __repr__(self):
        return "<%s('%s','%s')>" % (self.__tablename__, self.email, self.password)
