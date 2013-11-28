
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class Name(Base):
    __tablename__ = 'Name'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))

    def __init__(self, name):
        self.email = email

    def __repr__(self):
        return "<%s('%s','%s')>" % (self.__tablename__, self.name)
