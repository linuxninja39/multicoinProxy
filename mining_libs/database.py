from sqlalchemy import schema, create_engine
from sqlalchemy.orm import sessionmaker
from model import models as models
dbEngine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost/MultiPool', echo=True)
Session = sessionmaker(bind=dbEngine)
session = Session()
preferred_pools = "'stratum.bitcoin.cz','mint.bitminter.com'"


def get_worker(host, port, username, password=None):

    worker = session.execute(
        "\
        SELECT DISTINCT Worker.id, Worker.name, Worker.password, ProxyUser.password as userpassword FROM Worker \
        LEFT JOIN User ON Worker.userId = User.id \
        LEFT JOIN ProxyUser ON ProxyUser.userId = User.id \
        LEFT JOIN WorkerService ON WorkerService.workerId = Worker.id \
        LEFT JOIN Service ON Service.id = WorkerService.serviceId \
        LEFT JOIN Host ON Service.hostId = Host.id \
        WHERE ProxyUser.username = :username AND Service.port = :port AND Host.name = :host \
        ",
        {'host': host, 'port': port, 'username': username}
    ).first()
    if worker:
        if password:
            if password == worker['userpassword']:
                return {'remoteUsername': worker['name'], 'remotePassword': worker['password']}
            else:
                return None
        else:
            return {'remoteUsername': worker['name'], 'remotePassword': worker['password']}
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
        AND Host.name != :host_name \
",
        # AND Host.name IN (" + preferred_pools +") AND Host.name != :host_name \
        {'host_name': host}
    ).first()
    return pool


def get_pools():
    pools = session.execute(
        " \
        SELECT Service.id as id, Host.name as host, Service.port as port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Coin.profitability = (SELECT MAX(c.profitability) FROM Coin c) \
        "
    )
    return pools


def get_pool(worker_name, pool_id):
    pool = session.execute(
        " \
        SELECT Service.id as id, Host.name as host, Service.port as port From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN WorkerService ON WorkerService.serviceId = Service.id \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        WHERE Worker.name = :worker_name and Service.id = :pool_id\
        ",
        {
            'worker_name': worker_name,
            'pool_id': pool_id
        }
    ).first()
    return pool


def get_pool_by_id(pool_id):
    pool = session.execute(
        " \
        SELECT Service.id as id, Host.name as host, Service.port as port From Service \
        JOIN Host ON Service.hostId = Host.id \
        WHERE Service.id = :pool_id\
        ",
        {
            'pool_id': pool_id
        }
    ).first()
    return pool


def get_pool_id_by_host_and_port(host, port):
    pool = session.execute(
        " \
        SELECT Service.id as id, Host.name as host, Service.port as port From Service \
        JOIN Host ON Service.hostId = Host.id \
        WHERE Service.port = :port AND Host.name = :host\
        ",
        {
            'host': host,
            'port': port
        }
    ).first()
    return pool


def get_pool_by_worker_name_and_password(worker_name, worker_password):
    pool = session.execute(
        " \
        SELECT Service.id as id, Host.name as host, Service.port as port From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN WorkerService ON WorkerService.serviceId = Service.id \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN User ON Worker.userId = User.id \
        JOIN UserCoin ON UserCoin.userId = User.id AND UserCoin.coinId = Coin.id \
        WHERE Coin.profitability = (SELECT MAX(c.profitability) FROM Coin c) \
        AND Worker.name = :worker_name AND Worker.password = :worker_password AND UserCoin.mine = TRUE\
        ",

        {
            'worker_name': worker_name,
            'worker_password': worker_password
        }
    ).first()
    return pool


def get_best_pool_and_worker_by_proxy_user(proxy_username, proxy_password):
    pool = session.execute(
        " \
        SELECT Service.id as id, Host.name as host, Service.port as port, Worker.name as username, Worker.password From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN WorkerService ON WorkerService.serviceId = Service.id \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN User ON Worker.userId = User.id \
        JOIN UserCoin ON UserCoin.userId = User.id AND UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = User.id \
        WHERE Coin.profitability = (SELECT MAX(c.profitability) FROM Coin c) \
        AND ProxyUser.username = :proxy_username AND ProxyUser.password = :proxy_password AND UserCoin.mine = TRUE\
        ", # Order by added temporarily

        {
            'proxy_username': proxy_username,
            'proxy_password': proxy_password
        }
    ).first()
    return pool