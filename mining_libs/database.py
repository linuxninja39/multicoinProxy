from sqlalchemy import schema, create_engine
from sqlalchemy.orm import sessionmaker
from model import models as models
dbEngine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost/MultiPool', echo=True)
Session = sessionmaker(bind=dbEngine)
session = Session()
preferred_pools = "'stratum.bitcoin.cz','mint.bitminter.com'"
def get_worker(host, port, username, password = None):

    worker = session.execute(
        "SELECT DISTINCT Worker.id, Worker.name, Worker.password, User.password as userpassword FROM Worker LEFT JOIN User ON Worker.userId = User.id LEFT JOIN WorkerService ON WorkerService.workerId = Worker.id LEFT JOIN Service ON Service.id = WorkerService.serviceId LEFT JOIN Host ON Service.hostId = Host.id WHERE User.username = :username AND Service.port = :port AND Host.name = :host",
        {'host' : host, 'port' : port, 'username' : username}
    ).first()
    if worker:
        if password:
            if password == worker['userpassword']:
                return {'remoteUsername' : worker['name'], 'remotePassword' : worker['password']}
            else:
                return None
        else:
            return {'remoteUsername' : worker['name'], 'remotePassword' : worker['password']}
    else:
        return None

def get_best_coin(host):
    pool = session.execute(
        " \
        SELECT Host.name as host, Service.port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Coin.profitability = (SELECT MAX(c.profitability) FROM Coin c) \
        AND Host.name IN (" + preferred_pools +") AND Host.name != :host_name\
        ",
        { 'host_name' : host }
    ).first()
    return pool
