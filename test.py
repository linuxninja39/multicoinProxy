#!/usr/bin/env python2

from mining_libs.connection_pool import ConnectionPool
from mining_libs.user_mapper import UserMapper
from mining_libs.client_service import ClientMiningService

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from model.user import User
from model.coin import Coin
from model.user_coin import UserCoin
import pprint

Base = declarative_base()
Session = sessionmaker()

def main():

	engine = create_engine('mysql+mysqldb://root@localhost/MultiPool', echo=True)


	Session.configure(bind=engine)
	session = Session();
	
	user = User('bob@bob.com1', 'password')
	
	fUser = session\
			.query(User)\
			.filter_by(email=user.email)\
			.first();

	print user;

	if not fUser:
		session.add(user);
		session.commit();
		
	print fUser;

if __name__ == "__main__":
    main()
