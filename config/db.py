from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pprint

Session = sessionmaker()

dbEngine = create_engine('mysql+mysqldb://root@localhost/MultiPool', echo=True)

Session.configure(bind=dbEngine)
