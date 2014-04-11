from stratum.connection_registry import ConnectionRegistry
import weakref

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
from stratum import pubsub


class Connections(dict):
    def get(self, key):
        if key in self:
            return self[key]

    def set(self, key, value):
        # if key not in self:
        #     self[key] = []
        self[key] = value

    def unset(self, key):
        if key in self:
            self.pop(key, None)

    # def remove(self, key, value):
    #     if key in self:
    #         if value in self[key]:
    #             self[key].remove(value)
    #             if len(self[key]) == 0:
    #                 self.unset(key)

    def has(self, key, value=None):
        if key in self:
            if value:
                if value in self[key]:
                    return self[key]
                else:
                    return False
        return False


class CustomSocketTransportClientFactory(SocketTransportClientFactory):
    extranonce1 = None
    extranonce2_size = 4  # Temporarily
    tail_iterator = 0
    registered_tails = []
    mining_subscription = None  # stratum_listener.py MiningSubscription
    difficulty_subscription = None  # stratum_listener.py DifficultySubscription
    job_registry = None  # jobs.py JobRegistry
    workers = []  # worker.py Workers
    ip = None  # current proxy's IP Address
    conn_name = None
    connected = False
    pool = None  # ConnectionPool
    users = {}
    connections = Connections()  # For listing all connected users
    usernames = {}
    cp = None

    def __init__(self, host, port, allow_trusted=True, allow_untrusted=False, debug=False, signing_key=None,
                 signing_id=None, is_reconnecting=True, proxy=None, event_handler=client_service.ClientMiningService, conn_name=None, cp=None):
        self.debug = debug
        self.cp = cp
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
        self.pubsub = Pubsub()
        self.pubsub.f = self
        # self.users = {}
        # self.new_users = []

    def rpc(self, method, params, *args, **kwargs):
        if not self.client:
            raise custom_exceptions.TransportException("Not connected")

        return self.client.rpc(method, params, *args, **kwargs)

    def set_mining_subscription(self, mining_subscription=None):
        if mining_subscription is None:
            self.mining_subscription = MiningSubscription()
            self.mining_subscription.f = self
        else:
            self.mining_subscription = mining_subscription
        return self.mining_subscription

    def set_difficulty_subscription(self, difficulty_subscription=None):
        if difficulty_subscription is None:
            self.difficulty_subscription = DifficultySubscription()
            self.difficulty_subscription.f = self
        else:
            self.difficulty_subscription = difficulty_subscription
        return self.difficulty_subscription

    def set_job_registry(self, job_registry):
        self.job_registry = job_registry


class Pubsub(object):
    __subscriptions = {}
    f = None

    # @classmethod
    def subscribe(self, connection, subscription, key=None):
        if connection == None:
            raise custom_exceptions.PubsubException("Subscriber not connected")

        if not key:
            key = subscription.get_key()
        session = ConnectionRegistry.get_session(connection)
        if session == None:
            raise custom_exceptions.PubsubException("No session found")

        subscription.connection_ref = weakref.ref(connection)
        session.setdefault('subscriptions', {})

        if key in session['subscriptions']:
            self.unsubscribe(connection, subscription, key)  # very bad hack :(
            # raise custom_exceptions.AlreadySubscribedException("This connection is already subscribed for such event.")

        session['subscriptions'][key] = subscription

        self.__subscriptions.setdefault(subscription.event, weakref.WeakKeyDictionary())
        self.__subscriptions[subscription.event][subscription] = None

        if hasattr(subscription, 'after_subscribe'):
            if connection.on_finish != None:
                # If subscription is processed during the request, wait to
                # finish and then process the callback
                connection.on_finish.addCallback(subscription.after_subscribe)
            else:
                # If subscription is NOT processed during the request (any real use case?),
                # process callback instantly (better now than never).
                subscription.after_subscribe(True, f=self.f)

        # List of 2-tuples is prepared for future multi-subscriptions
        return ((subscription.event, key),)

    # @classmethod
    def unsubscribe(self, connection, subscription=None, key=None):
        if connection == None:
            raise custom_exceptions.PubsubException("Subscriber not connected")

        session = ConnectionRegistry.get_session(connection)
        if session == None:
            raise custom_exceptions.PubsubException("No session found")

        if subscription:
            key = subscription.get_key()

        try:
            # Subscription don't need to be removed from cls.__subscriptions,
            # because it uses weak reference there.
            del session['subscriptions'][key]
        except KeyError:
            print "Warning: Cannot remove subscription from connection session"
            return False

        return True

    # @classmethod
    def get_subscription_count(self, event):
        return len(self.__subscriptions.get(event, {}))

    # @classmethod
    def get_subscription(self, connection, event, key=None):
        '''Return subscription object for given connection and event'''
        session = ConnectionRegistry.get_session(connection)
        if session == None:
            raise custom_exceptions.PubsubException("No session found")

        if key == None:
            sub = [ sub for sub in session.get('subscriptions', {}).values() if sub.event == event ]
            try:
                return sub[0]
            except IndexError:
                raise custom_exceptions.PubsubException("Not subscribed for event %s" % event)

        else:
            raise Exception("Searching subscriptions by key is not implemented yet")

    # @classmethod
    def iterate_subscribers(self, event):
        for subscription in self.__subscriptions.get(event, weakref.WeakKeyDictionary()).iterkeyrefs():
            subscription = subscription()
            if subscription == None:
                # Subscriber is no more connected
                continue

            yield subscription

    # @classmethod
    def emit(self, event, *args, **kwargs):
        count = 0
        f = kwargs.get('f', None)
        for subscription in self.iterate_subscribers(event):
            if subscription.f.conn_name == f.conn_name:
                subscription.emit_single(*args, **kwargs)
