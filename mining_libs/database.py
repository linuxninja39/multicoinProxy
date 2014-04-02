from sqlalchemy import schema, create_engine
from sqlalchemy.orm import sessionmaker
import stratum
from model import models
dbEngine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost/MultiPool', echo=False)
Session = sessionmaker(bind=dbEngine)
session = Session()
log = stratum.logger.get_logger('proxy')


def get_worker(host, port, username, pool_id, password=None):
    # log.info(host, port, username, password)
    worker = session.execute(
        "\
        SELECT DISTINCT Worker.id, Worker.name, Worker.password, ProxyUser.password AS userpassword FROM Worker \
        LEFT JOIN User ON Worker.userId = User.id \
        LEFT JOIN ProxyUser ON ProxyUser.userId = User.id \
        LEFT JOIN WorkerService ON WorkerService.workerId = Worker.id \
        LEFT JOIN Service ON Service.id = WorkerService.serviceId \
        LEFT JOIN Host ON Service.hostId = Host.id \
        WHERE ProxyUser.username = :username AND Service.id = :pool_id \
        ",
        {'host': host, 'port': port, 'username': username, 'pool_id': str(pool_id)}
    ).first()
    # log.info(worker)
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


# def get_worker(host, port, username, pool_id, password=None):
#     worker = session.execute(
#         "\
#         SELECT DISTINCT Worker.id, Worker.name, Worker.password FROM Worker \
#         JOIN WorkerService ON WorkerService.serviceId = :pool_id \
#         JOIN Worker ON Worker.id = WorkerService.workerId \
#         ",
#         {'host': host, 'port': port, 'username': username, 'pool_id': str(pool_id)}
#     ).first()
#     # log.info(worker)
#     if worker:
#         if password:
#             if password == worker['userpassword']:
#                 return {'remoteUsername': worker['name'], 'remotePassword': worker['password']}
#             else:
#                 return None
#         else:
#             return {'remoteUsername': worker['name'], 'remotePassword': worker['password']}
#     else:
#         return None


def get_best_coin(host):
    pool = session.execute(
        " \
        SELECT Host.name AS host, Service.port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Coin.profitability = (SELECT MAX(c.profitability) FROM Coin c) \
        AND Host.name != :host_name \
",
        # AND Host.name IN (" + preferred_pools +") AND Host.name != :host_name \
        {'host_name': host}
    ).first()
    # log.info(pool)
    return pool


def get_pools():
    pools = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Service.active = TRUE \
        "
    )
    # log.info(pools)
    return pools


def get_pool(worker_name, pool_id):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port From Service \
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
    # log.info(pool)
    return pool


def get_pool_by_id(pool_id):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port From Service \
        JOIN Host ON Service.hostId = Host.id \
        WHERE Service.id = :pool_id\
        ",
        {
            'pool_id': pool_id
        }
    ).first()
    # log.info(pool)
    return pool


def get_pool_id_by_host_and_port(host, port):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port From Service \
        JOIN Host ON Service.hostId = Host.id \
        WHERE Service.port = :port AND Host.name = :host\
        ",
        {
            'host': host,
            'port': port
        }
    ).first()
    # log.info(pool)
    return pool


def get_pool_by_worker_name_and_password(worker_name, worker_password):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port From Service \
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
    # log.info(pool)
    return pool


def get_best_pool_and_worker_by_proxy_user(proxy_username, proxy_password):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port, Worker.name AS username, Worker.password From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN WorkerService ON WorkerService.serviceId = Service.id \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN User ON Worker.userId = User.id \
        JOIN UserCoin ON UserCoin.userId = User.id AND UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = User.id \
        WHERE Coin.profitability = ( \
            SELECT MAX(Coin.profitability) FROM ProxyUser \
            JOIN Worker ON Worker.userId = ProxyUser.userId \
            JOIN WorkerService ON WorkerService.workerId = Worker.id \
            JOIN Service ON Service.id = WorkerService.serviceId \
            JOIN CoinService ON CoinService.serviceId = Service.id \
            JOIN Coin ON Coin.id = CoinService.coinId \
            JOIN UserCoin ON UserCoin.coinId = Coin.id \
            WHERE UserCoin.mine = TRUE \
            AND ProxyUser.username = :proxy_username \
            AND ProxyUser.password = :proxy_password \
            ) \
        AND ProxyUser.username = :proxy_username AND ProxyUser.password = :proxy_password AND UserCoin.mine = TRUE \
        ", # Order by added temporarily
        {
            'proxy_username': proxy_username,
            'proxy_password': proxy_password
        }
    ).first()
    # log.info(pool)
    return pool


def get_current_pool_and_worker_by_proxy_user(proxy_username, proxy_password):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port, Worker.name AS username, Worker.password From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN WorkerService ON WorkerService.serviceId = Service.id \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN User ON Worker.userId = User.id \
        JOIN UserCoin ON UserCoin.userId = User.id AND UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = User.id \
        WHERE ProxyUser.username = :proxy_username AND ProxyUser.password = :proxy_password AND UserCoin.mine = TRUE \
        AND WorkerService.active = TRUE \
        ", # Order by added temporarily

        {
            'proxy_username': proxy_username,
            'proxy_password': proxy_password
        }
    ).first()
    # log.info(pool)
    return pool


def get_list_of_switch_users():
    users = session.execute(
        " \
        SELECT Service.id AS pool_id, Host.name AS host, Service.port AS port, \
        Worker.id as worker_id, Worker.name AS worker_username, Worker.password AS worker_password, \
        ProxyUser.username AS proxy_username, Coin.profitability, MAX(Coin.profitability), Coin.name From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN WorkerService ON WorkerService.serviceId = Service.id \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN UserCoin ON UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = UserCoin.userId \
        JOIN Worker ON Worker.id = WorkerService.workerId AND Worker.userId = UserCoin.userId \
        JOIN User ON User.id = ProxyUser.userId \
        JOIN (\
            SELECT Coin.profitability, ProxyUser.username FROM Service \
            JOIN Host ON Service.hostId = Host.id \
            JOIN WorkerService ON WorkerService.serviceId = Service.id \
            JOIN CoinService ON CoinService.serviceId = Service.id \
            JOIN Coin ON Coin.id = CoinService.coinId \
            JOIN UserCoin ON UserCoin.coinId = Coin.id \
            JOIN ProxyUser ON ProxyUser.userId = UserCoin.userId \
            JOIN Worker ON Worker.id = WorkerService.workerId AND Worker.userId = UserCoin.userId \
            AND UserCoin.mine = TRUE \
            AND WorkerService.active = TRUE \
            ) SL ON ProxyUser.username = SL.username \
        WHERE Coin.profitability > SL.profitability \
        AND UserCoin.mine = TRUE \
        AND WorkerService.active = FALSE \
        GROUP BY proxy_username \
        ",
    ).fetchall()
    log.info(users)
    return users


def get_list_of_active_users():
    users = session.execute(
        " \
        SELECT Service.id AS pool_id, Worker.name AS worker_username, Worker.password AS worker_password, ProxyUser.username AS proxy_username, TRUE AS used FROM Worker \
        JOIN WorkerService ON WorkerService.workerId = Worker.id \
        JOIN Service ON Service.id = WorkerService.serviceId \
        JOIN User ON User.id = Worker.userId \
        JOIN ProxyUser ON ProxyUser.userId = User.id \
        WHERE WorkerService.active = TRUE \
        ",
    ).fetchall()
    # log.info(users)
    return users


def activate_user_worker(worker_username, worker_password, pool_id):
    update = session.execute(
        " \
        UPDATE WorkerService \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        JOIN Service ON Service.id = WorkerService.serviceId \
        SET WorkerService.active = 1 \
        WHERE Worker.name = :worker_username AND Worker.password = :worker_password AND Service.id = :pool_id \
        ",
        {
            'worker_username': worker_username,
            'worker_password': worker_password,
            'pool_id': pool_id
        }
    )
    session.flush()
    session.commit()


def activate_user(proxy_username, pool_id):
    update = session.execute(
        " \
        UPDATE UserCoin \
        SET UserCoin.active = TRUE \
        WHERE UserCoin.userId = (SELECT User.id FROM User JOIN ProxyUser ON ProxyUser.userId = User.id WHERE ProxyUser.username = :proxy_username ) \
        AND UserCoin.coinId = (SELECT CoinService.coinId FROM CoinService WHERE CoinService.serviceId = :pool_id ) \
        ",
        {
            'proxy_username': proxy_username,
            'pool_id': pool_id
        }
    )
    session.flush()
    session.commit()


def deactivate_all_users_on_pool_start(pool_id):
    _ = session.execute(
        " \
        UPDATE WorkerService \
        SET WorkerService.active = 0 \
        WHERE WorkerService.id = :pool_id \
        ",
        {
            'pool_id': pool_id
        }
    )
    session.flush()
    session.commit()


def deactivate_all_users():
    _ = session.execute(
        " \
        UPDATE WorkerService \
        SET WorkerService.active = 0 \
        ",
    )
    session.flush()
    session.commit()


def increase_accepted_shares(worker_name, pool_id):
    _ = session.execute(
        " \
        UPDATE WorkerService \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        SET WorkerService.accepted = WorkerService.accepted + 1 \
        WHERE WorkerService.serviceId = :pool_id AND Worker.name = :worker_name \
        ",
        {
            'pool_id': pool_id,
            'worker_name': worker_name
        }
    )
    session.flush()
    session.commit()


def increase_rejected_shares(worker_name, pool_id):
    _ = session.execute(
        " \
        UPDATE WorkerService \
        JOIN Worker ON Worker.id = WorkerService.workerId \
        SET WorkerService.rejected = WorkerService.accepted + 1 \
        WHERE WorkerService.serviceId = :pool_id AND Worker.name = :worker_name \
        ",
        {
            'pool_id': pool_id,
            'worker_name': worker_name
        }
    )
    session.flush()
    session.commit()


def add_new_job(job_id, extranonce2_size_pool, extranonce1, pool_id, pool_name):
    _ = session.execute(
        " \
        INSERT INTO tempJob (job_id, extranonce2_size_pool, extranonce1, pool_id, pool_name) \
        VALUES (:job_id, :extranonce2_size_pool, :extranonce1, :pool_id, :pool_name) \
        ",
        {
            'job_id': job_id,
            'extranonce2_size_pool': extranonce2_size_pool,
            'extranonce1': extranonce1,
            'pool_id': pool_id,
            'pool_name': pool_name
        }
    )
    # log.info('here')
    session.flush()
    session.commit()


def update_job(job_id, worker_name, extranonce2, extranonce2_size_user, accepted):
    _ = session.execute(
        " \
        UPDATE tempJob \
        SET extranonce2_size_user = :extranonce2_size_user, accepted = :accepted, \
        worker_name = :worker_name, extranonce2 = :extranonce2 \
        WHERE tempJob.job_id = :job_id \
        ",
        {
            'job_id': job_id,
            'extranonce2_size_user': extranonce2_size_user,
            'extranonce2': extranonce2,
            'worker_name': worker_name,
            'accepted': accepted,
        }
    )
    # log.info('here')
    session.flush()
    session.commit()