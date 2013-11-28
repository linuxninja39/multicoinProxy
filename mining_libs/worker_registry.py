import time

import stratum.logger
from mining_libs.user_mapper import UserMapper

log = stratum.logger.get_logger('proxy')

class WorkerRegistry(object):
	userMapper = UserMapper()

	def __init__(self, f):
		self.f = f # Factory of Stratum client
		self.clear_authorizations()

	def clear_authorizations(self):
		self.authorized = []
		self.unauthorized = []
		self.last_failure = 0

	def _on_authorized(self, result, worker_name):
		if result == True:
			self.authorized.append(worker_name)
		else:
			self.unauthorized.append(worker_name)
		return result

	def _on_failure(self, failure, worker_name):
		log.exception("Cannot authorize worker '%s'" % worker_name)
		self.last_failure = time.time()

	def authorize(self, worker_name, password):
		if worker_name in self.authorized:
			return True

		if worker_name in self.unauthorized and time.time() - self.last_failure < 60:
			# Prevent flooding of mining.authorize() requests 
			log.warning("Authentication of worker '%s' with password '%s' failed, next attempt in few seconds..." % \
					(worker_name, password))
			return False

		remoteUser = self.userMapper.getUser(worker_name, password)
		if not remoteUser:
			log.warning("Couldn't map user '%s' with password '%s'" % (worker_name, password))
			self._on_failure('', worker_name)
			return False

		log.info("Local user/pass '%s:%s'. Remote user/pass '%s:%s'" % \
				(worker_name, password, remoteUser['remoteUser'], remoteUser['remotePassword'])
				)

		d = self.f.rpc('mining.authorize', [remoteUser['remoteUser'], remoteUser['remotePassword']])
		d.addCallback(self._on_authorized, worker_name)
		d.addErrback(self._on_failure, worker_name)
		return d

	def is_authorized(self, worker_name):
		return (worker_name in self.authorized)

	def is_unauthorized(self, worker_name):
		return (worker_name in self.unauthorized)  
