
from config.db import Session
from config.db import dbEngine
from sqlalchemy.ext.declarative import declarative_base
import re

Base = declarative_base()
Base.metadata.bind = dbEngine
Base.metadata.reflect()

Tables = {}

for t in Base.metadata.sorted_tables:
	n = t.name.encode('ascii')
	table = type(n, (Base,), dict(__table__ = t))
	Tables[n] = table
