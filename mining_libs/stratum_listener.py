import time
import binascii

from twisted.internet import defer

from stratum.services import GenericService
from stratum.pubsub import Pubsub, Subscription
from stratum.custom_exceptions import ServiceException, RemoteServiceException

#new import
from twisted.internet import reactor, defer
from stratum.socket_transport import SocketTransportFactory
from mining_libs.custom_classes import CustomSocketTransportClientFactory as SocketTransportClientFactory
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
#end new import
from jobs import JobRegistry

import stratum.logger
from mining_libs.user_mapper import UserMapper

log = stratum.logger.get_logger('proxy')

class UpstreamServiceException(ServiceException):
    code = -2

class SubmitException(ServiceException):
    code = -2

class DifficultySubscription(Subscription):
    event = 'mining.set_difficulty'
    difficulty = 1
    
    @classmethod
    def on_new_difficulty(cls, new_difficulty):
        cls.difficulty = new_difficulty
        cls.emit(new_difficulty)
    
    def after_subscribe(self, *args):
        self.emit_single(self.difficulty)
        
class MiningSubscription(Subscription):
    '''This subscription object implements
    logic for broadcasting new jobs to the clients.'''
    
    event = 'mining.notify'
    
    last_broadcast = None
    
    @classmethod
    def disconnect_all(cls):
        for subs in Pubsub.iterate_subscribers(cls.event):
            subs.connection_ref().transport.loseConnection()
        
    @classmethod
    def on_template(cls, job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs):
        '''Push new job to subscribed clients'''
        cls.last_broadcast = (job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs)
        cls.emit(job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs)
        
    def _finish_after_subscribe(self, result):
        '''Send new job to newly subscribed client'''
        try:        
            (job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, _) = self.last_broadcast
        except Exception:
            log.error("Template not ready yet")
            return result
        
        self.emit_single(job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, True)
        return result
             
    def after_subscribe(self, *args):
        '''This will send new job to the client *after* he receive subscription details.
        on_finish callback solve the issue that job is broadcasted *during*
        the subscription request and client receive messages in wrong order.'''
        self.connection_ref().on_finish.addCallback(self._finish_after_subscribe)
        
class StratumProxyService(GenericService):
    service_type = 'mining'
    service_vendor = 'mining_proxy'
    is_default = True
    userMapper = UserMapper()
    
    _f = None # Factory of upstream Stratum connection
    _cp = None # Connection Pool of factories of upstream Stratum connection
    extranonce1 = None
    extranonce2_size = None
    tail_iterator = 0
    registered_tails= []
    
    @classmethod
    def _set_upstream_factory(cls, f):
        cls._f = f
        cls._cp = f

    @classmethod
    def _set_extranonce(cls, extranonce1, extranonce2_size):
        cls.extranonce1 = extranonce1
        cls.extranonce2_size = extranonce2_size
        
    @classmethod
    def _get_unused_tail(cls):
        '''Currently adds only one byte to extranonce1, 
        limiting proxy for up to 255 connected clients.'''
        
        for _ in range(256): # 0-255
            cls.tail_iterator += 1
            cls.tail_iterator %= 255

            # Zero extranonce is reserved for getwork connections
            if cls.tail_iterator == 0:
                cls.tail_iterator += 1

            tail = binascii.hexlify(chr(cls.tail_iterator))

            if tail not in cls.registered_tails:
                cls.registered_tails.append(tail)
                return (tail, cls.extranonce2_size-1)
            
        raise Exception("Extranonce slots are full, please disconnect some miners!")
    
    def _drop_tail(self, result, tail):
        if tail in self.registered_tails:
            self.registered_tails.remove(tail)
        else:
            log.error("Given extranonce is not registered1")
        return result
            
    @defer.inlineCallbacks
    def authorize(self, proxyusername, password, *args):
        # log.info(worker_name + ' ' + worker_password)
        # worker = self.userMapper.getUser(worker_name, worker_password, self._f.main_host[0] + ':' + str(self._f.main_host[1]))
        pool_worker = database.get_best_pool_and_worker_by_proxy_user(proxyusername, password)
        # worker = database.get_worker(self._f.main_host[0], self._f.main_host[1], worker_name, worker_password)
        if not pool_worker:
            log.info("User with local user/pass '%s:%s' doesn't have an account on our proxy" % (proxyusername, password))
            defer.returnValue(False)

        log.info("Local user/pass '%s:%s'. Remote user/pass '%s:%s' on '%s:%d' pool" % \
            (proxyusername, password, pool_worker['username'], pool_worker['password'], pool_worker['host'], pool_worker['port'])
        )
        self._f = database.get_pool(pool_worker['username'], pool_worker['id'])
        if self._f.client is None or not self._f.client.connected:
            yield self._f.on_connect
                        
        result = (yield self._f.rpc('mining.authorize', [pool_worker['username'], pool_worker['password']]))
        log.info(result)
        defer.returnValue(result)
    
    @defer.inlineCallbacks
    def subscribe(self, *args):    
        if self._f.client == None or not self._f.client.connected:
            yield self._f.on_connect
            
        if self._f.client == None or not self._f.client.connected:
            raise UpstreamServiceException("Upstream not connected")
         
        if self.extranonce1 == None:
            # This should never happen, because _f.on_connect is fired *after*
            # connection receive mining.subscribe response
            raise UpstreamServiceException("Not subscribed on upstream yet")
        
        (tail, extranonce2_size) = self._get_unused_tail()
        
        session = self.connection_ref().get_session()
        session['tail'] = tail
                
        # Remove extranonce from registry when client disconnect
        self.connection_ref().on_disconnect.addCallback(self._drop_tail, tail)

        subs1 = Pubsub.subscribe(self.connection_ref(), DifficultySubscription())[0]
        subs2 = Pubsub.subscribe(self.connection_ref(), MiningSubscription())[0]            
        defer.returnValue(((subs1, subs2),) + (self.extranonce1+tail, extranonce2_size))
            
    @defer.inlineCallbacks
    def submit(self, worker_name, job_id, extranonce2, ntime, nonce, *args):
        f = self._cp.gwc(worker_name=worker_name, id=job_id, job=True)
        if not f:
            defer.returnValue(False)
        worker = database.get_worker(host=f.host, port=f.port, username=worker_name)
        if worker:
            worker_name = worker['remoteUsername']
        else:
            defer.returnValue(False)
        if f.client is None or not f.client.connected:
            raise SubmitException("Upstream not connected")

        session = self.connection_ref().get_session()
        tail = session.get('tail')
        if tail == None:
            raise SubmitException("Connection is not subscribed")
        
        start = time.time()
        # worker_name = self.userMapper.getWorkerName(worker_name, self._f.main_host[0] + ':' + str(self._f.main_host[1]))
        # pool = database.get_pool(worker_name, job_id, job=True)
        # if not pool:
        #     defer.returnValue(False)

        try:
            result = (yield f.rpc('mining.submit', [worker_name, job_id, tail+extranonce2, ntime, nonce]))
        except RemoteServiceException as exc:
            response_time = (time.time() - start) * 1000
            log.info("[%dms] Share from '%s' REJECTED: %s" % (response_time, worker_name, str(exc)))
            raise SubmitException(*exc.args)

        response_time = (time.time() - start) * 1000
        log.info("[%dms] Share from '%s' accepted, diff %d" % (response_time, worker_name, DifficultySubscription.difficulty))
        defer.returnValue(result)
