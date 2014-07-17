from sqlalchemy import schema, create_engine
from sqlalchemy.orm import sessionmaker
import stratum
import stratum.logger
# from model import models

dbEngine = create_engine("mysql+mysqldb://cg:as^$j23sn2@192.168.3.46:3306/cryptogods", echo=False)
Session = sessionmaker(bind=dbEngine)
log = stratum.logger.get_logger('proxy')


def get_worker(proxy_username, pool_id, password=None):
    """
    The worker credentials used to auth in the proxy are in the worker table
    """
    # log.info(host, port, username, password)
    log.info([proxy_username, pool_id])
    session = Session()
    worker = session.execute(
        "\
        SELECT Worker.id, ServiceUser.remoteWorkerName AS name, ServiceUser.remoteWorkerPass AS password, Worker.password AS userpassword FROM Worker \
        LEFT JOIN User ON Worker.userId = User.id \
        LEFT JOIN ServiceUser ON ServiceUser.userId = User.id \
        LEFT JOIN Service ON Service.id = ServiceUser.serviceId \
        WHERE Worker.name = :proxy_username AND Service.id = :pool_id AND Service.active = TRUE\
        ",
        {'proxy_username': proxy_username, 'pool_id': str(pool_id)}
    ).first()
    log.info(worker)
    session.close()
    if worker:
        if password:
            if password == worker['userpassword']:
                # return {'worker_name': worker['name'], 'worker_password': worker['password']}
                return [worker['name'], worker['password']]
            else:
                return None
        else:
            # return {'worker_name': worker['name'], 'worker_password': worker['password']}
            return [worker['name'], worker['password']]
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


def get_best_coin():
    session = Session()
    pool = session.execute(
        " \
        SELECT service.id as id, host.name AS host, service.port as port FROM service \
        JOIN coin on coin.id = service.coin_id \
        JOIN host ON host.id = service.host_id \
        WHERE coin.profitability = (SELECT MAX(c.profitability) FROM coin c JOIN service ON service.coin_id = c.id WHERE service.active = TRUE) \
        AND service.active = TRUE\
        ",
    ).first()
    log.info(pool)
    return pool


def get_best_coin_with_current_pool(pool_id):
    session = Session()
    session.commit()
    # log.info('session.expire_all()')
    pool = session.execute(
        " \
        SELECT Service.id as id, Host.name AS host, Service.port as port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Coin.profitability = (SELECT MAX(c.profitability) FROM Coin c JOIN CoinService cs ON cs.coinId = c.id) \
        AND Service.active = TRUE\
        ",
        {
            'pool_id': pool_id
        }
    ).first()
    log.info(pool)
    return pool


def get_pools():
    pools = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Service.active = TRUE AND Host.name != 'pool.d2.cc'\
        ORDER BY Coin.profitability DESC\
        "
    ).fetchall()
    # log.info(pools)
    return pools


def get_best_pool():
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port FROM Coin \
        JOIN CoinService ON CoinService.coinId = Coin.id \
        JOIN Service ON Service.id = CoinService.serviceId \
        JOIN Host ON Host.id = Service.hostId \
        WHERE Service.active = TRUE\
        "
    ).first()
    # log.info(pools)
    return pool

def get_pool(worker_name, pool_id):
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN ServiceUser ON ServiceUser.serviceId = Service.id \
        WHERE ServiceUser.remoteWorkerName = :worker_name and Service.id = :pool_id\
        ",
        {
            'worker_name': worker_name,
            'pool_id': pool_id
        }
    ).first()
    # log.info(pool)
    return pool


def get_pool_by_id(pool_id):
    session = Session()
    session.commit()
    pool = session.execute(
        " \
        SELECT service.id AS id, host.name AS host, service.port AS port FROM service \
        JOIN host ON service.host_id = host.id \
        WHERE service.id = :pool_id\
        ",
        {
            'pool_id': pool_id
        }
    ).first()
    # log.info(pool)
    return pool


def old_get_pool_id_by_host_and_port(host, port):
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


def get_pool_id_by_host_and_port(host, port):
    session = Session()
    pool = session.execute(
        " \
        SELECT service.id AS id, host.name AS host, service.port AS port FROM service \
        JOIN host ON service.host_id = host.id \
        WHERE service.port = :port AND host.name = :host\
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
        SELECT Service.id AS id, Host.name AS host, Service.port AS port, ServiceUser.remoteWorkerName AS username, ServiceUser.remoteWorkerPass as password From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN ServiceUser ON ServiceUser.serviceId = Service.id \
        JOIN Worker ON Worker.userId = ServiceUser.userId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN User ON Worker.userId = User.id \
        JOIN UserCoin ON UserCoin.userId = User.id AND UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = User.id \
        WHERE Coin.profitability = ( \
            SELECT MAX(Coin.profitability) FROM Worker \
            JOIN User ON User.id = Worker.userId \
            JOIN ServiceUser ON ServiceUser.userId = User.id \
            JOIN Service ON Service.id = ServiceUser.serviceId \
            JOIN CoinService ON CoinService.serviceId = Service.id \
            JOIN Coin ON Coin.id = CoinService.coinId \
            JOIN UserCoin ON UserCoin.coinId = Coin.id \
            WHERE UserCoin.mine = TRUE \
            AND Worker.name = :proxy_username \
            AND Worker.password = :proxy_password \
            AND Service.active = TRUE \
            ) \
        AND Worker.name = :proxy_username AND Worker.password = :proxy_password \
        AND Service.active = TRUE AND UserCoin.mine = TRUE \
        ",  # Order by added temporarily
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
        SELECT Service.id AS id, Host.name AS host, Service.port AS port, ServiceUser.remoteWorkerName AS username, ServiceUser.remoteWorkerPass as password From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN ServiceUser ON ServiceUser.serviceId = Service.id \
        JOIN Worker ON Worker.userId = ServiceUser.userId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN UserCoin ON UserCoin.userId = ServiceUser.userId AND UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = ServiceUser.userId \
        WHERE Worker.name = :proxy_username AND Worker.password = :proxy_password AND UserCoin.mine = TRUE \
        AND ServiceUser.active = TRUE \
        ",
        {
            'proxy_username': proxy_username,
            'proxy_password': proxy_password,
        }
    ).first()
    log.info(pool)
    return pool


def old_get_current_pool_and_worker_by_proxy_user_and_pool_id(proxy_username, proxy_password, pool_id):
    session = Session()
    pool = session.execute(
        " \
        SELECT Service.id AS id, Host.name AS host, Service.port AS port, ServiceUser.remoteWorkerName AS username, ServiceUser.remoteWorkerPass as password From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN ServiceUser ON ServiceUser.serviceId = Service.id \
        JOIN Worker ON Worker.userId = ServiceUser.userId \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN UserCoin ON UserCoin.userId = ServiceUser.userId AND UserCoin.coinId = Coin.id \
        JOIN ProxyUser ON ProxyUser.userId = ServiceUser.userId \
        WHERE Worker.name = :proxy_username AND Worker.password = :proxy_password AND UserCoin.mine = TRUE \
        AND Service.id = :pool_id \
        ",
        {
            'proxy_username': proxy_username,
            'proxy_password': proxy_password,
            'pool_id': pool_id
        }
    ).first()
    log.info(pool)
    session.close()
    return pool


def get_current_pool_and_worker_by_proxy_user_and_pool_id(proxy_username, proxy_password, pool_id):
    try:
        [user_name, worker_name] = proxy_username.split('.')
        session = Session()
        pool = session.execute(
            " \
            SELECT service.id AS id, host.name AS host, service.port AS port, :worker_name AS username, workers_group.password as password From service \
            JOIN host ON service.host_id = host.id \
            JOIN worker ON worker.user_id = user.id \
            JOIN workers_group ON workers_group.id = worker.group_id \
            JOIN CoinService ON CoinService.serviceId = Service.id \
            JOIN Coin ON Coin.id = CoinService.coinId \
            JOIN UserCoin ON UserCoin.userId = ServiceUser.userId AND UserCoin.coinId = Coin.id \
            JOIN ProxyUser ON ProxyUser.userId = ServiceUser.userId \
            WHERE Worker.name = :proxy_username AND Worker.password = :proxy_password AND UserCoin.mine = TRUE \
            AND Service.id = :pool_id \
            ",
            {
                'proxy_username': proxy_username,
                'proxy_password': proxy_password,
                'pool_id': pool_id
            }
        ).first()
        log.info(pool)
        session.close()
        return pool
    except IndexError:
        return None


def get_list_of_switch_users():
    users = session.execute(
        " \
        SELECT Service.id AS pool_id, Host.name AS host, Service.port AS port, \
        ServiceUser.id as worker_id, ServiceUser.remoteWorkerName AS worker_username, ServiceUser.remoteWorkerPass AS worker_password, \
        Worker.name AS proxy_username, Worker.name as proxy_password, Coin.profitability, MAX(Coin.profitability), Coin.name From Service \
        JOIN Host ON Service.hostId = Host.id \
        JOIN ServiceUser ON ServiceUser.serviceId = Service.id \
        JOIN CoinService ON CoinService.serviceId = Service.id \
        JOIN Coin ON Coin.id = CoinService.coinId \
        JOIN UserCoin ON UserCoin.coinId = Coin.id \
        JOIN Worker ON Worker.userId = ServiceUser.userId \
        JOIN User ON User.id = Worker.userId \
        JOIN (\
            SELECT Coin.profitability, Worker.name FROM Service \
            JOIN Host ON Service.hostId = Host.id \
            JOIN ServiceUser ON ServiceUser.serviceId = Service.id \
            JOIN CoinService ON CoinService.serviceId = Service.id \
            JOIN Coin ON Coin.id = CoinService.coinId \
            JOIN UserCoin ON UserCoin.coinId = Coin.id \
            JOIN Worker ON Worker.userId = ServiceUser.userId \
            AND UserCoin.mine = TRUE \
            AND ServiceUser.active = TRUE \
            ) SL ON Worker.name = SL.name \
        WHERE Coin.profitability > SL.profitability \
        AND UserCoin.mine = TRUE \
        AND ServiceUser.active = FALSE \
        GROUP BY proxy_username \
        ",
    ).fetchall()
    log.info(users)
    return users


def get_list_of_active_users():
    users = session.execute(
        " \
        SELECT Service.id AS pool_id, ServiceUser.remoteWorkerName AS worker_username, ServiceUser.remoteWorkerPass AS worker_password, Worker.name AS proxy_username, TRUE AS used FROM ServiceUser \
        JOIN Service ON Service.id = ServiceUser.serviceId \
        JOIN Worker ON Worker.userId = ServiceUser.id \
        WHERE ServiceUser.active = FALSE \
        ",
    ).fetchall()
    # log.info(users)
    return users


def activate_user_worker(worker_username, worker_password, pool_id):
    update = session.execute(
        " \
        UPDATE ServiceUser \
        JOIN Service ON Service.id = ServiceUser.serviceId \
        SET ServiceUser.active = 1 \
        WHERE ServiceUser.remoteWorkerName = :worker_username AND ServiceUser.remoteWorkerPass = :worker_password AND Service.id = :pool_id \
        ",
        {
            'worker_username': worker_username,
            'worker_password': worker_password,
            'pool_id': pool_id
        }
    )
    session.flush()
    session.commit()


def deactivate_user_worker(worker_username, worker_password, pool_id):
    update = session.execute(
        " \
        UPDATE ServiceUser \
        JOIN Service ON Service.id = ServiceUser.serviceId \
        SET ServiceUser.active = 0 \
        WHERE ServiceUser.remoteWorkerName = :worker_username AND ServiceUser.remoteWorkerPass = :worker_password AND Service.id = :pool_id \
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
        UPDATE ServiceUser \
        SET ServiceUser.active = 0 \
        WHERE ServiceUser.serviceId = :pool_id \
        ",
        {
            'pool_id': pool_id
        }
    )
    session.flush()
    session.commit()


def check_switch():
    switch = session.execute(
        " \
        SELECT switch from Switch where Switch.switch = True \
        "
    ).first()
    if switch:
        return True
    return False


def deactivate_all_users():
    _ = session.execute(
        " \
        UPDATE ServiceUser \
        SET ServiceUser.active = 0 \
        ",
    )
    session.flush()
    session.commit()


def increase_accepted_shares(worker_name, pool_id):
    _ = session.execute(
        " \
        UPDATE ServiceWorker \
        JOIN Worker ON Worker.id = ServiceWorker.workerId \
        JOIN User ON User.id = Worker.userId \
        JOIN ServiceUser ON ServiceUser.userId = User.Id AND ServiceUser.serviceId = ServiceWorker.serviceId \
        SET ServiceWorker.acceptedShares = ServiceWorker.acceptedShares + 1 \
        WHERE ServiceWorker.serviceId = :pool_id AND ServiceUser.remoteWorkerName = :worker_name \
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
        UPDATE ServiceWorker \
        JOIN Worker ON Worker.id = ServiceWorker.workerId \
        JOIN User ON User.id = Worker.userId \
        JOIN ServiceUser ON ServiceUser.userId = User.Id AND ServiceUser.serviceId = ServiceWorker.serviceId \
        SET ServiceWorker.rejectedShares = ServiceWorker.rejectedShares + 1 \
        WHERE ServiceWorker.serviceId = :pool_id AND ServiceUser.remoteWorkerName = :worker_name \
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


"""
For example, we run proxy with parameter "-sw 300". 300 - time in seconds = 5 minutes.
When proxy starts working we have next coin's profitability.
id: Coin Name   -- profitability
03: Feathercoin -- 1
04: Litecoin    -- 5
11: Bitcoin     -- 6
12: ELACoin     -- 1
13: Phoenixcoin -- 7
14: Worldcoin   -- 2
15: NovaCoin    -- 8
16: LuckyCoin   -- 3


We run cgminer for user "bob1". This user has accounts on both Feathercoint and Litecoin pools.
As you can see, the most profitable coin for this user is Litecoin, so we connect "bob1" to corresponding pool.
If you want to switch current user, you have to change Featercoin profitability and it should be greater then
current user's active coin. In our situation, it should be > 5. So if you will change Feather coin, for example,
to 6, user will be switched to new pool (when switch function will be executed). After a period of time he will get new work from this pool.
As I understand, it's need some time to mine all old work, sent to cgminer. It seems, that it has a queue of works there.

I tested switch today, using instructions described above. And everything was ok.
"""
