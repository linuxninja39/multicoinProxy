from stratum.socket_transport import SocketTransportFactory
from twisted.internet import defer
from mining_libs.custom_classes import CustomSocketTransportClientFactory as SocketTransportClientFactory
from mining_libs import database, jobs
from mining_libs import worker_registry
import stratum.logger
from mining_libs import stratum_listener
log = stratum.logger.get_logger('proxy')


@defer.inlineCallbacks
def new_on_connect(f):
    '''Callback when proxy get connected to the pool'''
    log.info("Connected to Stratum pool at %s:%d" % f.main_host)
    #reactor.callLater(30, f.client.transport.loseConnection)

    # Hook to on_connect again
    f.on_connect.addCallback(new_on_connect)

    # Every worker have to re-autorize
    f.workers.clear_authorizations()

    # if args.custom_user:
    #     log.warning("Authorizing custom user %s, password %s" % (args.custom_user, args.custom_password))
    #     f.workers.authorize(args.custom_user, args.custom_password)

    # Subscribe for receiving jobs
    log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    # for i in range(1, 10):
    #     log.info('subscribing')
    #     log.info('subscribing')
    #     log.info('subscribing')
    #     (_, extranonce1, extranonce2_size) = (yield f.rpc('mining.subscribe', []))[:3]
        # log.info('extranonce1: ' + str(extranonce1))
        # log.info('extranonce2_size: ' + str(extranonce2_size))
        # log.info('subscribing')
        # log.info('subscribing')
        # log.info('subscribing')
    (_, extranonce1, extranonce2_size) = (yield f.rpc('mining.subscribe', []))[:3]
    log.info(extranonce1)
    log.info(extranonce2_size)
    # job_registry.set_extranonce(extranonce1, extranonce2_size)
    # stratum_listener.StratumProxyService._set_extranonce(extranonce1, extranonce2_size)
    f.job_registry.set_extranonce(extranonce1, extranonce2_size)
    log.info(f.extranonce1)
    log.info(f.extranonce2_size)
    stratum_listener.StratumProxyService._set_extranonce(f, extranonce1, extranonce2_size)
    log.info(f.extranonce1)
    log.info(f.extranonce2_size)

    defer.returnValue(f)


def on_disconnect(f, workers, job_registry):
    '''Callback when proxy get disconnected from the pool'''
    log.info("Disconnected from Stratum pool at %s:%d" % f.main_host)
    f.on_disconnect.addCallback(on_disconnect, workers, job_registry)

    # stratum_listener.MiningSubscription.disconnect_all()
    f.mining_subscription.disconnect_all()
    # Reject miners because we don't give a *job :-)
    workers.clear_authorizations()

    return f


def new_on_disconnect(f):
    '''Callback when proxy get disconnected from the pool'''
    log.info("Disconnected from Stratum pool at %s:%d" % f.main_host)
    f.on_disconnect.addCallback(new_on_disconnect)

    # stratum_listener.MiningSubscription.disconnect_all()
    f.mining_subscription.disconnect_all()
    database.deactivate_all_users_on_pool_start(f.conn_name)

    # Reject miners because we don't give a *job :-)
    f.workers.clear_authorizations()
    # f.close_connection(f.conn_name)
    # defer.returnValue(f)
    return f
    # yield f

class ConnectionPool():
    _connections = {}
    debug = False
    proxy = None
    event_handler = None
    job_registry = None
    workers = None
    cmd = None
    no_midstate = None
    real_target = None
    use_old_target = None
    new_users = {}
    on_connect_callback = None
    on_disconnect_callback = None
    users = {}
    usernames = {}

    def __init__(self, debug,
                 # proxy,
                 cmd, no_midstate, real_target, use_old_target):
        self.debug = debug
        # self.proxy = proxy
        self.cmd = cmd
        # self.event_handler = event_handler
        self.no_midstate = no_midstate
        self.real_target = real_target
        self.use_old_target = use_old_target

    def get_connection(
            self,
            conn_name=None,
            host=None,
            port=None,
            ip=None
    ):
        log.info("getConnection")
        if conn_name is None:
            if ip:
                conn_name = self.get_pool_by_ip(ip)
                log.info(ip)
                log.info(conn_name)
            if conn_name is None:
                pool = database.get_pool_id_by_host_and_port(host, port)
                if pool:
                    conn_name = pool['id']

        if conn_name in self._connections.keys():
            return self._connections[conn_name]
        else:
            return self._new_connection(
                host=host,
                port=port,
            )

    def has_connection(
            self,
            conn_name=None,
            host=None,
            port=None,
            ip=None
    ):
        log.info("getConnection")
        if conn_name is None:
            if ip:
                conn_name = self.get_pool_by_ip(ip)
                log.info(ip)
                log.info(conn_name)
            if conn_name is None:
                pool = database.get_pool_id_by_host_and_port(host, port)
                if pool:
                    conn_name = pool['id']

        if conn_name in self._connections.keys():
            return self._connections[conn_name]
        else:
            return None

    def _new_connection(
            self,
            host,
            port,
            conn_name=None,
    ):
        if conn_name is None:
            log.info(host)
            log.info(port)
            conn_name = database.get_pool_id_by_host_and_port(host, port)['id']
            log.info(conn_name)
        self._connections[conn_name] = SocketTransportClientFactory(host=host, port=port, debug=self.debug,
                                                                    conn_name=conn_name
                                                                    # , proxy=self.proxy
        )
        self._connections[conn_name].job_registry = jobs.JobRegistry(  # Creating JobRegistry for new Socket
                                                                       self._connections[conn_name],
                                                                       cmd=self.cmd,
                                                                       no_midstate=self.no_midstate,
                                                                       real_target=self.real_target,
                                                                       use_old_target=self.use_old_target
        )
        self._connections[conn_name].workers = worker_registry.WorkerRegistry(self._connections[conn_name])
        self._connections[conn_name].workers.set_host(host, port)
        self._connections[conn_name].pool = self
        self._connections[conn_name].on_connect.addCallback(new_on_connect)
        # new_on_connect(self._connections[conn_name])
        self._connections[conn_name].on_disconnect.addCallback(new_on_disconnect)
        database.deactivate_all_users_on_pool_start(conn_name)
        return self._connections[conn_name]

    def close_conn(self, conn_name):
        self._connections.pop(conn_name, None)
        # return

    def init_all_pools(self):
        pools = database.get_pools()
        for pool in pools:
            self._new_connection(host=pool['host'], port=pool['port'])
        return self

    def init_one_pool(self):
        pools = database.get_pools()
        for pool in pools:
            self._new_connection(host=pool['host'], port=pool['port'])
            break
        return self

    def get_pool_by_ip(self, ip):
        for conn_name in self._connections:
            # log.info(self._connections[conn_name].ip + '------' + ip)
            if self._connections[conn_name].ip == ip:
                return conn_name
        pools = database.get_pools()
        import socket
        for pool in pools:
            pool_ip = socket.gethostbyname(pool['host'])
            pool_ip = ip.split(':')[0]
            if pool_ip == ip:
                return pool['id']
        return None

    def gwc(self, worker_name=None, worker_password=None, id=None, job=True):
        """
        Get SocketTransportClientFactory for selected worker, using his worker_name and current job_id
        job_id contains information about current pool: it's ID
        """
        if id:
            check = False
            # try:
            if job:
                pool_id = id.split('_')[-1]
                test = int(pool_id) + 1
            else:
                pool_id = id
            pool_info = database.get_pool_by_id(pool_id)
            pool = self.get_connection(pool_info['id'], pool_info['host'], pool_info['port'])
            # return pool.on_connect
            return pool
            # except TypeError:
            #     return self._connections.itervalues().next()  # Temporarily
        elif worker_name and worker_password:
            pool = database.get_pool_by_worker_name_and_password(worker_name, worker_password)
            return self._connections[pool['id']]

    # def add_on_connect_callback(self, on_connect, workers, job_registry):
    def add_on_connect_callback(self, on_connect, workers, job_registry):
        for conn in self._connections:
            conn.on_connect.addCallback(on_connect, workers, job_registry)

    def add_on_disconnect_callback(self, on_disconnect, workers, job_registry):
        for conn in self._connections:
            conn.on_disconnect.addCallback(on_disconnect, workers, job_registry)

    def on_shutdown(self):
        for conn in self._connections:
            conn.is_reconnecting = False  # Don't let stratum factory to reconnect again

    def on_connect(self):
        for conn in self._connections:
            conn.yield_on_connect(conn)

    def on_connect_cb(self, callback):
        for conn in self._connections:
            self._connections[conn].on_connect.addCallback(callback)

    def on_disconnect_cb(self, callback):
        for conn in self._connections:
            self._connections[conn].on_disconnect.addCallback(callback)

    def yield_on_connect(conn):
        yield conn.on_connect
