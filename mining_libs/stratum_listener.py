import time
import binascii

from twisted.internet import defer

from stratum.services import GenericService
from stratum.pubsub import Pubsub, Subscription
from stratum.custom_exceptions import ServiceException, RemoteServiceException

#new import
from twisted.internet import reactor, defer
from stratum.services import ServiceEventHandler
# from twisted.web.server import Site
#
# from mining_libs import stratum_listener
# from mining_libs import getwork_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import worker_registry
from mining_libs import multicast_responder
from mining_libs import version
from mining_libs import utils
from mining_libs import database
import struct
#end new import
from jobs import JobRegistry

import stratum.logger
from mining_libs.user_mapper import UserMapper

log = stratum.logger.get_logger('proxy')

def var_int(i):
    if i <= 0xff:
        return struct.pack('>B', i)
    elif i <= 0xffff:
        return struct.pack('>H', i)
    raise Exception("number is too big")


class UpstreamServiceException(ServiceException):
    code = -2


class SubmitException(ServiceException):
    code = -2


class DifficultySubscription(Subscription):
    event = 'mining.set_difficulty'
    difficulty = 1
    f = None

    # @classmethod
    def on_new_difficulty(self, new_difficulty, **kwargs):
        self.difficulty = new_difficulty
        self.emit(new_difficulty, **kwargs)

    def emit(self, *args, **kwargs):
        '''Shortcut for emiting this event to all subscribers.'''
        if not hasattr(self, 'event'):
            raise Exception("Subscription.emit() can be used only for subclasses with filled 'event' class variable.")
        return self.f.pubsub.emit(self.event, *args, **kwargs)

    def after_subscribe(self, *args):
        self.emit_single(self.difficulty, f=self.f)

    def emit_single(self, *args, **kwargs):
        '''Perform emit of this event just for current subscription.'''
        # log.info('difficulty subscription - emit single')
        # log.info('mining subscription - emit single')
        # log.info('mining subscription - emit single')
        # log.info('mining subscription - emit single')
        conn = self.connection_ref()
        if conn == None:
            # Connection is closed
            return
        f = kwargs.get('f', None)
        f = self.f
        try:
            if f:
                ident = conn.get_ident()
                # log.info(ident)
                # log.info(f.users)
                if conn.get_ident() in f.users:
                    payload = self.process(*args, **kwargs)
                    if payload:
                        if isinstance(payload, (tuple, list)):
                            conn.writeJsonRequest(self.event, payload, is_notification=True)
                            self.after_emit(*args, **kwargs)
                        else:
                            raise Exception("Return object from process() method must be list or None")
        except AttributeError:
            i = 1


class MiningSubscription(Subscription):
    '''This subscription object implements
    logic for broadcasting new jobs to the clients.'''

    event = 'mining.notify'

    last_broadcast = None
    f = None
    # @classmethod
    # def disconnect_all(cls):
    #     for subs in Pubsub.iterate_subscribers(cls.event):
    #         subs.connection_ref().transport.loseConnection()

    def disconnect_all(self):
        for subs in self.f.pubsub.iterate_subscribers(self.event):
            if subs.connection_ref():
                if subs.connection_ref().transport:
                    subs.connection_ref().transport.loseConnection()

    # @classmethod
    # def on_template(cls, job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs):
    #     '''Push new job to subscribed clients'''
    #     cls.last_broadcast = (job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs)
    #     cls.emit(job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs)

    def on_template(self, job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs, **kwargs):
        '''Push new job to subscribed clients'''
        # log.info('mining_subscription')
        # log.info(self)
        # log.info(id(self))
        self.last_broadcast = (job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs)
        self.emit(job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs, **kwargs)

    def _finish_after_subscribe(self, result, f):
        '''Send new job to newly subscribed client'''
        try:
            (job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, _) = self.last_broadcast
        except Exception:
            log.error("Template not ready yet")
            return result

        self.emit_single(job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, True, f = f)
        return result

    def after_subscribe(self, f, *args):
        '''This will send new job to the client *after* he receive subscription details.
        on_finish callback solve the issue that job is broadcasted *during*
        the subscription request and client receive messages in wrong order.'''
        self.connection_ref().on_finish.addCallback(self._finish_after_subscribe, f=f)

    def emit(self, *args, **kwargs):
        '''Shortcut for emiting this event to all subscribers.'''
        if not hasattr(self, 'event'):
            raise Exception("Subscription.emit() can be used only for subclasses with filled 'event' class variable.")
        return self.f.pubsub.emit(self.event, *args, **kwargs)

    def emit_single(self, *args, **kwargs):
        '''Perform emit of this event just for current subscription.'''
        conn = self.connection_ref()
        if conn == None:
            # Connection is closed
            return
        f = kwargs.get('f', None)
        f = self.f
        try:
            if f:
                ident = conn.get_ident()
                # log.info(ident)
                # log.info(f.users)
                if conn.get_ident() in f.users:
                    payload = self.process(*args, **kwargs)
                    if payload != None:
                        if isinstance( payload, (tuple, list)):
                            conn.writeJsonRequest(self.event, payload, is_notification=True)
                            self.after_emit(*args, **kwargs)
                        else:
                            raise Exception("Return object from process() method must be list or None")
        except AttributeError:
            i = 1


class StratumProxyService(GenericService):
    service_type = 'mining'
    service_vendor = 'mining_proxy'
    is_default = True
    userMapper = UserMapper()

    _f = None  # Factory of upstream Stratum connection
    extranonce1 = None
    extranonce2_size = None
    tail_iterator = 0
    registered_tails = []
    unsubscribed_users = {}

    @classmethod
    def _set_upstream_factory(cls, f):
        cls._f = f
        cls._cp = f

    # @classmethod
    # def _set_extranonce(cls, extranonce1, extranonce2_size):
    #     cls.extranonce1 = extranonce1
    #     cls.extranonce2_size = extranonce2_size
    #
    # @classmethod
    # def _get_unused_tail(cls):
    #     '''Currently adds only one byte to extranonce1,
    #     limiting proxy for up to 255 connected clients.'''
    #
    #     for _ in range(256): # 0-255
    #         cls.tail_iterator += 1
    #         cls.tail_iterator %= 255
    #
    #         # Zero extranonce is reserved for getwork connections
    #         if cls.tail_iterator == 0:
    #             cls.tail_iterator += 1
    #
    #         tail = binascii.hexlify(chr(cls.tail_iterator))
    #
    #         if tail not in cls.registered_tails:
    #             cls.registered_tails.append(tail)
    #             return (tail, cls.extranonce2_size-1)
    @classmethod
    def _set_extranonce(cls, f, extranonce1, extranonce2_size):
        f.extranonce1 = extranonce1
        f.extranonce2_size = extranonce2_size

    @classmethod
    def _get_unused_tail(self, f):
        '''Currently adds up to two bytes to extranonce1,
        limiting proxy for up to 65535 connected clients.'''

        for _ in range(0, 0xffff):  # 0-65535
            f.tail_iterator += 1
            f.tail_iterator %= 0xffff

            # Zero extranonce is reserved for getwork connections
            if f.tail_iterator == 0:
                f.tail_iterator += 1

            # var_int throws an exception when input is >= 0xffff
            tail = var_int(f.tail_iterator)
            tail_len = len(tail)

            # tail = binascii.hexlify(chr(f.tail_iterator))

            if tail not in f.registered_tails:
                f.registered_tails.append(tail)
                return (binascii.hexlify(tail), f.extranonce2_size - tail_len)
                # return (tail, f.extranonce2_size-1)

        raise Exception("Extranonce slots are full, please disconnect some miners!")

    def _drop_tail(self, result, tail, f):
        if tail in f.registered_tails:
            f.registered_tails.remove(tail)
            f.users.pop(self.connection_ref().get_ident(), None)
        else:
            log.error("Given extranonce is not registered1")
        return result
    # @classmethod
    # def _drop_tail(cls, result, tail, f):
    #     log.info('drop_tail')
    #     log.info(result)
    #     log.info(tail)
    #     log.info(f)
    #     log.info('drop_tail')
    #     if tail in f.registered_tails:
    #         f.registered_tails.remove(tail)
    #     else:
    #         log.error("Given extranonce is not registered1")
    #     return result

    @defer.inlineCallbacks
    def authorize(self, proxyusername, password, *args):
        # log.info(worker_name + ' ' + worker_password)
        # worker = self.userMapper.getUser(worker_name, worker_password, self._f.main_host[0] + ':' + str(self._f.main_host[1]))
        if self.connection_ref().get_ident() in self._cp.new_users:
            pool_worker = database.get_best_pool_and_worker_by_proxy_user(proxyusername, password)
        else:
            pool_worker = database.get_current_pool_and_worker_by_proxy_user(proxyusername, password)
        # worker = database.get_worker(self._f.main_host[0], self._f.main_host[1], worker_name, worker_password)
        # log.info('authorize start')
        # log.info(self.connection_ref().get_ident())
        # log.info('authorize end')
        if not pool_worker:
            log.info("User with local user/pass '%s:%s' doesn't have an account on our proxy" % (proxyusername, password))
            defer.returnValue(False)

        log.info("Local user/pass '%s:%s'. Remote user/pass '%s:%s' on '%s:%d' pool" % \
            (proxyusername, password, pool_worker['username'], pool_worker['password'], pool_worker['host'], pool_worker['port'])
        )
        # log.info('AUTHORIZE METHOD HERE')
        pool_info = database.get_pool(pool_worker['username'], pool_worker['id'])
        f = self._cp.get_connection(host=pool_info['host'], port=pool_info['port'])
        # if self._f.client is None or not self._f.client.connected:
        if f.client is None or not f.client.connected:
            yield f.on_connect
        # user_ident = self.connection_ref().get_ident()
        # if user_ident in self.unsubscribed_users:
        #     # d = defer.Deferred()
        #     # d.callback()
        #     self.new_subscribe(f)
        # log.info('SUBSCRIBE METHOD IN AUTHORIZE HERE')
        # log.info('SUBSCRIBE METHOD IN AUTHORIZE HERE')
        # log.info('SUBSCRIBE METHOD IN AUTHORIZE HERE')
        # log.info('SUBSCRIBE METHOD IN AUTHORIZE HERE')
        log.info('SUBSCRIBE METHOD IN AUTHORIZE HERE')
        log.info(self._cp.new_users)
        if self.connection_ref().get_ident() in self._cp.new_users:
            subs_keys = self._cp.new_users[self.connection_ref().get_ident()]
            log.info(subs_keys)
            subs1 = f.pubsub.subscribe(self.connection_ref(), f.difficulty_subscription, subs_keys[0])[0]
            # log.info(subs1)
            subs2 = f.pubsub.subscribe(self.connection_ref(), f.mining_subscription, subs_keys[1])[0]
            # log.info(subs2)
            tail = subs_keys[2]
            self._cp.new_users.pop(self.connection_ref().get_ident())
            database.activate_user_worker( pool_worker['username'], pool_worker['password'], f.conn_name)
            f.users[self.connection_ref().get_ident()] = {'proxyusername': proxyusername, 'password': password, 'pool_worker_username': pool_worker['username'], 'pool_worker_password': pool_worker['password'], 'conn_name': f.conn_name, 'tail': tail, 'conn_ref': self.connection_ref(), 'subs1': subs_keys[0], 'subs2': subs_keys[1], 'extranonce2_size': subs_keys[3]}
            # f.usernames[proxyusername][self.connection_ref().get_ident()] = f.users[self.connection_ref().get_ident()]
            if proxyusername not in f.usernames:
                f.usernames[proxyusername] = {'conn_name': f.conn_name, 'connections': []}
            if self.connection_ref().get_ident() not in f.usernames[proxyusername]['connections']:
                f.usernames[proxyusername]['connections'] += [self.connection_ref().get_ident(), ]
            f.connections.set(self.connection_ref().get_ident(), proxyusername)
            f.pool.users[self.connection_ref().get_ident()] = {'proxyusername': proxyusername, 'password': password, 'pool_worker_username': pool_worker['username'], 'pool_worker_password': pool_worker['password'], 'conn_name': f.conn_name, 'tail': tail, 'conn_ref': self.connection_ref(), 'subs1': subs_keys[0], 'subs2': subs_keys[1], 'extranonce2_size': subs_keys[3]}
            # f.pool.usernames[proxyusername] = f.pool.users[self.connection_ref().get_ident()]
            if proxyusername not in f.pool.usernames:
                f.pool.usernames[proxyusername] = {'conn_name': f.conn_name, 'connections': []}
            if self.connection_ref().get_ident() not in f.pool.usernames[proxyusername]['connections']:
                f.pool.usernames[proxyusername]['connections'] += [self.connection_ref().get_ident(), ]
            # f.pool.usernames[proxyusername] += [self.connection_ref().get_ident(), ]
            f.pool.connections.set(self.connection_ref().get_ident(), proxyusername)
        if self.connection_ref().get_ident() in self._cp.new_users:
            # f.difficulty_subscription.on_new_difficulty(f.difficulty_subscription.difficulty)  # Rework this, as this will affect all users
            f.difficulty_subscription.emit_single( f.difficulty_subscription.difficulty, f=f)
            # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
            # f.job_registry.set_difficulty(f.difficulty_subscription.difficulty)
        result = (yield f.rpc('mining.authorize', [pool_worker['username'], pool_worker['password']]))
        log.info([pool_worker['username'], pool_worker['password']])
        log.info(proxyusername)
        log.info(f.main_host)
        log.info(result)
        log.info(result)
        defer.returnValue(result)

    # @defer.inlineCallbacks
    # @defer.inlineCallbacks
    # def authorize(self, worker_name, worker_password, *args):
    #     # log.info(worker_name + ' ' + worker_password)
    #     worker = self.userMapper.getUser(worker_name, worker_password, self._f.main_host[0] + ':' + str(self._f.main_host[1]))
    #     if not worker:
    #         log.info("User with local user/pass '%s:%s' doesn't have an account on '%s:%d' pool" % \
    #         (worker_name, worker_password, self._f.main_host[0], self._f.main_host[1])
    #         )
    #         defer.returnValue(False)
    #
    #     log.info("Local user/pass '%s:%s'. Remote user/pass '%s:%s' on '%s:%d' pool" % \
    #         (worker_name, worker_password, worker['remoteUsername'], worker['remotePassword'], self._f.main_host[0], self._f.main_host[1])
    #     )
    #     if self._f.client is None or not self._f.client.connected:
    #         yield self._f.on_connect
    #
    #     result = (yield self._f.rpc('mining.authorize', [worker['remoteUsername'], worker['remotePassword']]))
    #     log.info(result)
    #     defer.returnValue(result)

    def new_subscribe(self, f):
        # log.info('new subscribe method')
        # log.info('new subscribe method')
        # log.info('new subscribe method')
        # log.info('new subscribe method')
        # log.info('new subscribe method')
        if f.client == None or not f.client.connected:
            yield f.on_connect

        # if self._f.client == None or not self._f.client.connected:
        if f.client == None or not f.client.connected:
            raise UpstreamServiceException("Upstream not connected")

        if f.extranonce1 == None:
            # This should never happen, because _f.on_connect is fired *after*
            # connection receive mining.subscribe response
            raise UpstreamServiceException("Not subscribed on upstream yet")

        (tail, extranonce2_size) = self._get_unused_tail(f)

        session = self.connection_ref().get_session()
        session['tail'] = tail

        # Remove extranonce from registry when client disconnect
        self.connection_ref().on_disconnect.addCallback(self._drop_tail, tail=tail, f=f)

        subs1 = f.pubsub.subscribe(self.connection_ref(), f.difficulty_subscription)[0]
        subs2 = f.pubsub.subscribe(self.connection_ref(), f.mining_subscription)[0]
        defer.returnValue(((subs1, subs2),) + (f.extranonce1+tail, extranonce2_size))

    @defer.inlineCallbacks
    def subscribe(self, *args):
        # log.info('qweqweqwe')
        # log.info(self.connection_ref())
        # log.info(self.connection_ref().get_session())
        # log.info(self._cp.workers.authorized)
        # log.info(self._cp.workers.unauthorized)
        # log.info('qweqweqwee')
        ip = self.connection_ref().proxied_ip or self.connection_ref().transport.getPeer().host
        port = self.connection_ref().transport.getPeer().port
            # if self.cp:
        # log.info(args)
        # log.info('ip=' + str(ip) + '  port=' + str(port))
        # log.info('subscribe start')
        # log.info(self.connection_ref().get_ident())
        self.unsubscribed_users[self.connection_ref().get_ident()] = False
        # log.info(self.unsubscribed_users)
        # log.info('subscribe end')
        if port > 4000:
            for conn in self._cp._connections:
                f = self._cp._connections[conn]
                # log.info('ffffffffffff')
                # log.info(f)
                # log.info(f.extranonce1)
                # log.info(f.extranonce2_size)
                # log.info('ffffffffffff')
                # if self._f.client == None or not self._f.client.connected:
                if f.client == None or not f.client.connected:
                    yield f.on_connect

                # if self._f.client == None or not self._f.client.connected:
                if f.client == None or not f.client.connected:
                    raise UpstreamServiceException("Upstream not connected")

                if f.extranonce1 == None:
                    # This should never happen, because _f.on_connect is fired *after*
                    # connection receive mining.subscribe response
                    raise UpstreamServiceException("Not subscribed on upstream yet")

                (tail, extranonce2_size) = self._get_unused_tail(f)

                session = self.connection_ref().get_session()
                session['tail'] = tail

                # Remove extranonce from registry when client disconnect
                self.connection_ref().on_disconnect.addCallback(self._drop_tail, tail=tail, f=f)

                subs1 = f.pubsub.subscribe(self.connection_ref(), f.difficulty_subscription)[0]
                # log.info(subs1)
                subs2 = f.pubsub.subscribe(self.connection_ref(), f.mining_subscription)[0]
                # log.info(subs2)
                self._cp.new_users[self.connection_ref().get_ident()] = (subs1[1], subs2[1], tail, extranonce2_size)
                # log.info(self._cp.new_users[self.connection_ref().get_ident()])
                log.info(((subs1, subs2),) + (f.extranonce1, extranonce2_size))
                # log.info('new users tail: ' + str(tail))
                # defer.returnValue(((subs1, subs2),) + (f.extranonce1, extranonce2_size))
                # f.pubsub.unsubscribe(self.connection_ref())
                f.pubsub.unsubscribe(self.connection_ref(), subscription=f.difficulty_subscription, key=subs1[1])
                f.pubsub.unsubscribe(self.connection_ref(), subscription=f.mining_subscription, key=subs2[1])
                # defer.returnValue(((subs1, subs2),) + (tail, extranonce2_size))
                defer.returnValue(((subs1, subs2),) + ('', extranonce2_size+1))
                # defer.returnValue(((subs1, subs2),) + (tail, 4))
        else:
            f = self._cp.get_connection(ip=ip, port=port)

            # if self._f.client == None or not self._f.client.connected:
            if f.client == None or not f.client.connected:
                yield f.on_connect

            # if self._f.client == None or not self._f.client.connected:
            if not f.client or not f.client.connected:
                raise UpstreamServiceException("Upstream not connected")

            if f.extranonce1 == None:
                # This should never happen, because _f.on_connect is fired *after*
                # connection receive mining.subscribe response
                raise UpstreamServiceException("Not subscribed on upstream yet")

            (tail, extranonce2_size) = self._get_unused_tail(f)

            session = self.connection_ref().get_session()
            session['tail'] = tail

            # Remove extranonce from registry when client disconnect
            self.connection_ref().on_disconnect.addCallback(self._drop_tail, tail=tail, f=f)

            subs1 = f.pubsub.subscribe(self.connection_ref(), f.difficulty_subscription)[0]
            subs2 = f.pubsub.subscribe(self.connection_ref(), f.mining_subscription())[0]
            # log.info('Subscribing to pool')
            # log.info('Subscribing to pool')
            # log.info('Subscribing to pool')
            # log.info('Subscribing to pool')
            # log.info(((subs1, subs2),) + (f.extranonce1+tail, extranonce2_size))
            defer.returnValue(((subs1, subs2),) + (f.extranonce1+tail, extranonce2_size))
        # subs1 = Pubsub.subscribe(self.connection_ref(), DifficultySubscription())[0]
        # subs2 = Pubsub.subscribe(self.connection_ref(), MiningSubscription())[0]
        # defer.returnValue(((subs1, subs2),) + (0+0, 0))
    # @defer.inlineCallbacks
    # def subscribe(self, *args):
    #     if self._f.client == None or not self._f.client.connected:
    #         yield self._f.on_connect
    #
    #     if self._f.client == None or not self._f.client.connected:
    #         raise UpstreamServiceException("Upstream not connected")
    #
    #     if self.extranonce1 == None:
    #         # This should never happen, because _f.on_connect is fired *after*
    #         # connection receive mining.subscribe response
    #         raise UpstreamServiceException("Not subscribed on upstream yet")
    #
    #     (tail, extranonce2_size) = self._get_unused_tail()
    #
    #     session = self.connection_ref().get_session()
    #     session['tail'] = tail
    #
    #     # Remove extranonce from registry when client disconnect
    #     self.connection_ref().on_disconnect.addCallback(self._drop_tail, tail)
    #
    #     subs1 = Pubsub.subscribe(self.connection_ref(), DifficultySubscription())[0]
    #     subs2 = Pubsub.subscribe(self.connection_ref(), MiningSubscription())[0]
    #     defer.returnValue(((subs1, subs2),) + (f.extranonce1+tail, extranonce2_size))

    @defer.inlineCallbacks
    def submit(self, worker_name, job_id, extranonce2, ntime, nonce, *args):
        # log.info('job_id')
        # log.info(job_id)
        # log.info('job_id')
        f = self._cp.gwc(worker_name=worker_name, id=job_id, job=True)
        # log.info(worker_name)
        job_id = job_id.split('_')[0]
        # log.info('new_job_id')
        # log.info(job_id)
        # log.info('new_job_id')
        # job_id = int(job_id)
        # log.info(('worker_name', 'job_id', 'extranonce2', 'ntime', 'nonce'))
        # log.info((worker_name, job_id, extranonce2, ntime, nonce))
        # log.info(args)
        # log.info('current_pool')
        # log.info(f)
        # log.info(f.conn_name)
        if f is None:
            defer.returnValue(False)
        proxy_username = worker_name
        worker = database.get_worker(host=f.main_host[0], port=f.main_host[1], username=worker_name, pool_id=str(f.conn_name))
        if worker:
            worker_name = worker['remoteUsername']
        else:
            # log.info('problem here')
            # log.info('problem here')
            log.info('problem here')
            defer.returnValue(False)
        # log.info(worker_name)
        if f.client is None or not f.client.connected:
            raise SubmitException("Upstream not connected")

        session = self.connection_ref().get_session()
        try:
            # log.info(self.connection_ref().get_ident())
            # log.info(self._cp.users)
            # log.info(self._cp.users[self.connection_ref().get_ident()])
            tail = self._cp.users[self.connection_ref().get_ident()]['tail']
        except KeyError:
            tail = session.get('tail')
        if tail == None:
            raise SubmitException("Connection is not subscribed")

        # worker_name = self.userMapper.getWorkerName(worker_name, self._f.main_host[0] + ':' + str(self._f.main_host[1]))
        # pool = database.get_pool(worker_name, job_id, job=True)
        # if not pool:
        #     defer.returnValue(False)
        # log.info('pool extranonce2_size')
        # log.info(f.extranonce2_size)
        # log.info('user extranonce2_size')
                    # user_extranonce2_size = f.users[self.connection_ref().get_ident()]['extranonce2_size']
        # log.info(user_extranonce2_size)
        # log.info('pool extranonce1')
        # log.info(f.extranonce1)
        # log.info('old extranonce2')
        # log.info(extranonce2)
        # log.info('new extranonce2')
        # extranonce2 = self.extranonce2_padding(extranonce2, f.extranonce2_size, user_extranonce2_size)
        # extranonce2 = str(struct.unpack('>I', struct.pack('>I', int(extranonce2)))[0])
        # log.info(extranonce2)
        start = time.time()
        # log.info(str(job_id) + '   ' + str(worker_name) + '   ' + str(extranonce2))
        log.info(str(job_id) + '   ' + str(worker_name) + '   ' + str(extranonce2))
        # log.info(str(job_id) + '   ' + str(worker_name) + '   ' + str(extranonce2))
        try:
            log.info('submitting: ' + str(self.connection_ref().get_ident()) + '  --  ' + str(tail) + '  --  ' + str(extranonce2))
            result = (yield f.rpc('mining.submit', [worker_name, job_id, extranonce2, ntime, nonce]))
        except RemoteServiceException as exc:
            response_time = (time.time() - start) * 1000
            database.increase_rejected_shares(worker_name, f.conn_name)
            log.info("[%dms] Share from '%s' using '%s' worker on %s:%d REJECTED: %s" % (response_time, proxy_username, worker_name, f.main_host[0], f.main_host[1], str(exc)))
            database.update_job(job_id, worker_name, extranonce2, 4, False)
            raise SubmitException(*exc.args)

        response_time = (time.time() - start) * 1000
        database.increase_accepted_shares(worker_name, f.conn_name)
        database.update_job(job_id, worker_name, extranonce2, 4, True)
        log.info("[%dms] Share from '%s' using '%s' worker on %s:%d accepted, diff %d" % (response_time, proxy_username, worker_name, f.main_host[0], f.main_host[1],  f.difficulty_subscription.difficulty))
        defer.returnValue(result)

    # @defer.inlineCallbacks
    # def submit(self, worker_name, job_id, extranonce2, ntime, nonce, *args):
    #     if self._f.client == None or not self._f.client.connected:
    #         raise SubmitException("Upstream not connected")
    #
    #     session = self.connection_ref().get_session()
    #     tail = session.get('tail')
    #     if tail == None:
    #         raise SubmitException("Connection is not subscribed")
    #
    #     start = time.time()
    #     worker_name = self.userMapper.getWorkerName(worker_name, self._f.main_host[0] + ':' + str(self._f.main_host[1]))
    #     try:
    #         result = (yield self._f.rpc('mining.submit', [worker_name, job_id, tail+extranonce2, ntime, nonce]))
    #     except RemoteServiceException as exc:
    #         response_time = (time.time() - start) * 1000
    #         log.info("[%dms] Share from '%s' REJECTED: %s" % (response_time, worker_name, str(exc)))
    #         raise SubmitException(*exc.args)
    #
    #     response_time = (time.time() - start) * 1000
    #     log.info("[%dms] Share from '%s' accepted, diff %d" % (response_time, worker_name, DifficultySubscription.difficulty))
    #     defer.returnValue(result)

    def extranonce2_padding(self, extranonce2, pool_extranonce2_size, user_extranonce2_size):
        '''Return extranonce2 with padding bytes'''

        extranonce2_bin = struct.pack('>I', int(str(extranonce2)), 16)
        missing_len = pool_extranonce2_size - len(user_extranonce2_size)

        if missing_len < 0:
            # extranonce2 is too long, we should print warning on console,
            # but try to shorten extranonce2
            log.info("Extranonce size mismatch. Please report this error to pool operator!")
            return extranonce2_bin[abs(missing_len):]

        # This is probably more common situation, but it is perfectly
        # safe to add whitespaces
        return '\x00' * missing_len + extranonce2_bin

    def get_transactions(self, *args):
        log.warn("mining.get_transactions isn't supported by proxy")
        return []

"""
Notes about extranonce2
to convert it from miner view - use:
new_extranonce2 = int(extranonce2, 16)
extranonce2_bin = struct.pack('>I', new_extranonce2)
add/remove zeroes, then and get final_extranonce2
extranonce2 = struct.unpack('>', final_extranonce2)
then format(extranonce2, 'x')



"""
