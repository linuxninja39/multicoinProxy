__author__ = 'melnichevv'

from stratum.socket_transport import SocketTransportClientFactory
from twisted.internet.protocol import ServerFactory
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, defer, endpoints
from stratum_listener import MiningSubscription, DifficultySubscription
# import socksclient
from stratum import custom_exceptions
from stratum.protocol import Protocol, ClientProtocol
from stratum.event_handler import GenericEventHandler
import time
import binascii
from stratum import logger
log = logger.get_logger('proxy')
from mining_libs import client_service

class CustomSocketTransportClientFactory(SocketTransportClientFactory):
    extranonce1 = None
    extranonce2_size = None
    tail_iterator = 0
    registered_tails= []
    mining_subscription = None  # stratum_listener.py MiningSubscription
    difficulty_subscription = None  # stratum_listener.py DifficultySubscription
    job_registry = None  # jobs.py JobRegistry
    workers = []  # worker.py Workers
    ip = None  # current proxy's IP Address
    conn_name = None
    connected = False
    pool = None  # ConnectionPool

    def __init__(self, host, port, allow_trusted=True, allow_untrusted=False, debug=False, signing_key=None,
                 signing_id=None, is_reconnecting=True, proxy=None, event_handler=client_service.ClientMiningService, conn_name=None):
        self.debug = debug
        self.is_reconnecting = is_reconnecting
        self.signing_key = signing_key
        self.signing_id = signing_id
        self.client = None  # Reference to open connection
        self.on_disconnect = defer.Deferred()
        self.on_connect = defer.Deferred()
        self.peers_trusted = {}
        self.peers_untrusted = {}
        self.main_host = (host, port)
        self.new_host = None
        self.proxy = proxy
        self.event_handler = event_handler
        self.protocol = ClientProtocol
        self.after_connect = []
        self.conn_name = conn_name
        self.set_difficulty_subscription()
        self.set_mining_subscription()
        import socket
        ip = socket.gethostbyname(host)
        self.ip = ip.split(':')[0]
        self.connect()
        self.connected = False

    def rpc(self, method, params, *args, **kwargs):
        if not self.client:
            raise custom_exceptions.TransportException("Not connected")

        return self.client.rpc(method, params, *args, **kwargs)

    def set_mining_subscription(self, mining_subscription = None):
        if mining_subscription is None:
            self.mining_subscription = MiningSubscription()
        else:
            self.mining_subscription = mining_subscription
        return self.mining_subscription

    def set_difficulty_subscription(self, difficulty_subscription = None):
        if difficulty_subscription is None:
            self.difficulty_subscription = DifficultySubscription()
        else:
            self.difficulty_subscription = difficulty_subscription
        return self.difficulty_subscription

    def set_job_registry(self, job_registry):
        self.job_registry = job_registry