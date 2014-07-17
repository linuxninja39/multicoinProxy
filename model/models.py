#autogenerated by sqlautocode

from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relation

engine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost/MultiPool')
DeclarativeBase = declarative_base()
metadata = DeclarativeBase.metadata
metadata.bind = engine

CoinService = Table(u'CoinService', metadata,
    Column(u'id', INTEGER(), primary_key=True, nullable=False),
    Column(u'coinId', INTEGER(), ForeignKey('Coin.id'), nullable=False),
    Column(u'serviceId', INTEGER(), ForeignKey('Service.id'), nullable=False),
)

Service = Table(u'Service', metadata,
    Column(u'id', INTEGER(), primary_key=True, nullable=False),
    Column(u'serviceTypeId', INTEGER(), ForeignKey('ServiceType.id'), nullable=False),
    Column(u'port', INTEGER(), nullable=False),
    Column(u'hostId', INTEGER(), ForeignKey('Host.id'), nullable=False),
)

UserFirstName = Table(u'UserFirstName', metadata,
    Column(u'id', INTEGER(), primary_key=True, nullable=False),
    Column(u'userId', INTEGER(), ForeignKey('User.id'), nullable=False),
    Column(u'nameId', INTEGER(), ForeignKey('Name.id'), nullable=False),
)

WorkerCoin = Table(u'WorkerCoin', metadata,
    Column(u'id', INTEGER(), primary_key=True, nullable=False),
    Column(u'workerId', INTEGER(), ForeignKey('Worker.id'), nullable=False),
    Column(u'coinId', INTEGER(), ForeignKey('Coin.id'), nullable=False),
)

class Coin(DeclarativeBase):
    __tablename__ = 'Coin'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    name = Column(u'name', VARCHAR(length=150), nullable=False)
    profitability = Column(u'profitability', INTEGER(), nullable=False)
    symbol = Column(u'symbol', CHAR(length=3), nullable=False)

    #relation definitions


class CoinService(DeclarativeBase):
    __table__ = CoinService


    #relation definitions


class Domain(DeclarativeBase):
    __tablename__ = 'Domain'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    name = Column(u'name', VARCHAR(length=250), nullable=False)

    #relation definitions


class Email(DeclarativeBase):
    __tablename__ = 'Email'

    #column definitions
    domainId = Column(u'domainId', INTEGER(), ForeignKey('Domain.id'), nullable=False)
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    user = Column(u'user', VARCHAR(length=250), nullable=False)

    #relation definitions


class Host(DeclarativeBase):
    __tablename__ = 'Host'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    name = Column(u'name', VARCHAR(length=250), nullable=False)

    #relation definitions


class Name(DeclarativeBase):
    __tablename__ = 'Name'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    name = Column(u'name', VARCHAR(length=100), nullable=False)

    #relation definitions


class Service(DeclarativeBase):
    __table__ = Service


    #relation definitions


class ServiceType(DeclarativeBase):
    __tablename__ = 'ServiceType'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    name = Column(u'name', VARCHAR(length=250), nullable=False)

    #relation definitions


class User(DeclarativeBase):
    __tablename__ = 'User'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    password = Column(u'password', VARCHAR(length=250), nullable=False)
    username = Column(u'username', VARCHAR(length=250), nullable=False)

    #relation definitions


class UserFirstName(DeclarativeBase):
    __table__ = UserFirstName


    #relation definitions


class Worker(DeclarativeBase):
    __tablename__ = 'Worker'

    #column definitions
    id = Column(u'id', INTEGER(), primary_key=True, nullable=False)
    name = Column(u'name', VARCHAR(length=200), nullable=False)
    password = Column(u'password', VARCHAR(length=200), nullable=False)
    userId = Column(u'userId', INTEGER(), ForeignKey('User.id'), nullable=False)

    #relation definitions


class WorkerCoin(DeclarativeBase):
    __table__ = WorkerCoin


    #relation definitions


#example on how to query your Schema
from sqlalchemy.orm import sessionmaker
session = sessionmaker(bind=engine)()
objs = session.query(Coin).all()
# print 'All Coin objects: %s'%objs

print 'Trying to start IPython shell...',
try:
    from IPython.Shell import IPShellEmbed
    print 'Success! Press <ctrl-d> to exit.'
    print 'Available models:%s'%['Coin', 'CoinService', 'Domain', 'Email', 'Host', 'Name', 'Service', 'ServiceType', 'User', 'UserFirstName', 'Worker', 'WorkerCoin']
    print '\nTry something like: session.query(Coin).all()'
    ipshell = IPShellEmbed()
    ipshell()
except:
    'Failed. please easy_install ipython'
