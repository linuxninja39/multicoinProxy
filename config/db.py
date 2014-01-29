from sqlalchemy import schema, create_engine
from sqlalchemy.orm import sessionmaker
import pprint
import argparse
def load_src(name, fpath):
    import os, imp
    return imp.load_source(name, os.path.join(os.path.dirname(__file__), fpath))

load_src("models", "../model/models.py")
import models

def db_parse_args():
    db_parser = argparse.ArgumentParser(description='This proxy allows you to run getwork-based miners against Stratum mining pool.')
    db_parser.add_argument('-d', '--drop', dest='drop', action='store_true', help='Drop tables')
    db_parser.add_argument('-u', '--update', dest='update', action='store_true', help='Update tables')
    db_parser.add_argument('-a', '--add', dest='add', type=str, help='Add row to table')
    return db_parser.parse_args()

dbEngine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost/NewMultiPool', echo=True)

if __name__ == '__main__':
    db_args = db_parse_args()
    metadata = models.Base.metadata
    metadata.bind = dbEngine
    Session = sessionmaker(bind=dbEngine)
    session = Session()
    if db_args.drop:
        print 'DROPPING TABLES...'
        metadata.drop_all()
    if db_args.update:
        print 'CREATING TABLES...'
        metadata.create_all()
    if db_args.add != None or db_args.add != 'user':
        user = models.User()
        for property, value in vars(models.User).iteritems():
            if property[:1] != "_" and property != 'coins' and property != 'id':
                # print ("Enter %s:" , property)
                text = "Enter %s:" % property
                value = input(text)
                print(value)
                setattr(user, property, value)
                # user.property = value
        session.add(user)
        session.commit()

