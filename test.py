#!/usr/bin/env python2

from mining_libs.connection_pool import ConnectionPool
from mining_libs.user_mapper import UserMapper
from mining_libs.client_service import ClientMiningService

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.db import Session
from model.tables import Tables

import sys
import pprint

def main():

	session = Session()
	user = Tables['User']()
	user.username = 'linuxninja39'
	user.password = 'password'

	User = Tables['User']
	Worker = Tables['Worker']
	Coin = Tables['Coin']
	Host = Tables['Host']
	Service = Tables['Service']
	
	res = session\
		.query(User.username, Worker.name, Coin.name, Host.name, Service.port)\
		.join(Worker)\
		.join(Tables['WorkerCoin'])\
		.join(Tables['Coin'])\
		.join(Tables['CoinService'])\
		.join(Tables['Service'])\
		.join(Tables['Host'])\
		.filter(User.username==user.username)\
		.order_by(Coin.profitability.desc())\
		.first()

	pprint.pprint(res)

	worker = session.query(Worker).first();


if __name__ == "__main__":
    main()
