import time

import stratum.logger
from config.db import dbEngine
from mining_libs.user_mapper import UserMapper
from model.old_models import User
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_
from mining_libs import database

log = stratum.logger.get_logger('proxy')


class WorkerRegistry(object):
    userMapper = UserMapper()
    Session = sessionmaker(bind=dbEngine)
    session = Session()
    host = port = None

    def __init__(self, f):
        self.f = f  # Factory of Stratum client
        self.cp = f  # Connection Pool with Stratum client's factories
        self.clear_authorizations()

    def clear_authorizations(self):
        self.authorized = []
        self.unauthorized = []
        self.last_failure = 0

    def _on_authorized(self, result, worker_name):
        if result:
            self.authorized.append(worker_name)
        else:
            self.unauthorized.append(worker_name)
        return result

    def _on_failure(self, failure, worker_name):
        log.exception("Cannot authorize worker '%s'" % worker_name)
        self.last_failure = time.time()

    def set_host(self, host, port):
        self.host = host
        self.port = port

    # def authorize(self, worker_name, password):
    #     if worker_name in self.authorized:
    #         return True
    #
    #     if worker_name in self.unauthorized and time.time() - self.last_failure < 60:
    #         # Prevent flooding of mining.authorize() requests
    #         log.warning("Authentication of worker '%s' with password '%s' failed, next attempt in few seconds..." % \
    #                 (worker_name, password))
    #         return False
    #
    #     remote_user = self.session.query(User).filter_by(username = worker_name, password = password).one()
    #     log.warning("Trying to connect '%s' with password '%s'" % (worker_name, password))
    #     # remoteUser = self.userMapper.getUser(worker_name, password)
    #     if not remote_user:
    #         log.warning("Couldn't map user '%s' with password '%s'" % (worker_name, password))
    #         self._on_failure('', worker_name)
    #         return False
    #
    #     log.info("Local user/pass '%s:%s'. Remote user/pass '%s:%s'" % \
    #             (worker_name, password, remote_user.remote_username, remote_user.remote_password)
    #             )
    #
    #     d = self.f.rpc('mining.authorize', [remote_user.remote_username, remote_user.remote_password])
    #     d.addCallback(self._on_authorized, worker_name)
    #     d.addErrback(self._on_failure, worker_name)
    #     return d

    def authorize(self, proxyusername, password):
        log.info(proxyusername + ' ' + password)
        if proxyusername in self.authorized:
            return True

        if proxyusername in self.unauthorized and time.time() - self.last_failure < 60:
            # Prevent flooding of mining.authorize() requests
            log.warning("Authentication of user '%s' with password '%s' failed, next attempt in few seconds..." % \
                        (proxyusername, password))
            return False
        # worker = self.userMapper.getUser(worker_name, password, self.host)
        # worker = database.get_worker(self.host, self.port, proxyusername, password)
        pool_worker = database.get_best_pool_and_worker_by_proxy_user(proxyusername, password)
        if not pool_worker:
            # log.info("User with local user/pass '%s:%s' doesn't have an account on '%s:%d' pool" % \
            log.info("User with local user/pass '%s:%s' failed" % \
                     (proxyusername, password)
            )
            return False

        log.info("Local user/pass '%s:%s'. Remote user/pass '%s:%s' on '%s:%d' pool" % \
                 (proxyusername, password, pool_worker['username'], pool_worker['password'], pool_worker['host'], pool_worker['port'])
        )
        d = self.cp.gwc(worker_name=pool_worker['username'], worker_password=pool_worker['password'], id=pool_worker['id'], job_id=False).rpc('mining.authorize', [pool_worker['username'], pool_worker['password']])
        d.addCallback(self._on_authorized, pool_worker['username'])
        d.addErrback(self._on_failure, pool_worker['username'])
        return d

    def is_authorized(self, worker_name):
        return (worker_name in self.authorized)

    def is_unauthorized(self, worker_name):
        return (worker_name in self.unauthorized)

    def reauthorize_all(self):
        to_authorize = self.authorized + self.unauthorized
        self.clear_authorizations()
        password = 'SbvF3LLT'
        for worker in to_authorize:
            if worker:
                # log.info('Trying to authorize worker: %s:%s' % (worker, password))
                self.authorize(worker, password)

