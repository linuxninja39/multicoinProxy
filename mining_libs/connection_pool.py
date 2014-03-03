from stratum.socket_transport import SocketTransportFactory
from mining_libs.custom_classes import CustomSocketTransportClientFactory as SocketTransportClientFactory
from mining_libs import database, jobs


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

    def __init__(self, debug, proxy, event_handler, cmd, no_midstate, real_target, use_old_target):
        self.debug = debug
        self.proxy = proxy
        self.cmd = cmd
        self.no_midstate = no_midstate
        self.real_target = real_target
        self.use_old_target = use_old_target

    def get_connection(
            self,
            conn_name,
            host=None,
            port=None,
    ):
        print("getConnection")
        if conn_name in self._connections.keys():
            return self._connections[conn_name]
        else:
            return self._new_connection(
                conn_name,
                host=host,
                port=port,
            )

    def _new_connection(
            self,
            conn_name,
            host,
            port,
    ):
        self._connections[conn_name] = SocketTransportClientFactory(host, port, self.debug, self.proxy,
                                                                    self.event_handler)
        self._connections[conn_name].job_registry = jobs.JobRegistry(  # Creating JobRegistry for new Socket
            self._connections[conn_name],
            cmd=self.cmd,
            no_midstate=self.no_midstate,
            real_target=self.real_target,
            use_old_target=self.use_old_target
        )

        return self._connections[conn_name]

    def init_all_pools(self):
        pools = database.get_pools()
        for pool in pools:
            self._new_connection(pool['id'], pool['host'], pool['port'])
        return self

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
                test = pool_id + 1
            else:
                pool_id = id
            pool_info = database.get_pool_by_id(pool_id)
            pool = self.get_connection(pool_info['id'], pool_info['host'], pool_info['port'])
            return pool.on_connect
            # return pool
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

    def yield_on_connect(conn):
        yield conn.on_connect
