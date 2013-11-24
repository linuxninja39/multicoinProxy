from stratum.socket_transport import SocketTransportFactory, SocketTransportClientFactory

class ConnectionPool():
	_connections = {}
	def getConnection(
			self,
			connName,
			host=None,
			port=None,
			debug=False,
			proxy=None,
			event_handler=None
			):
		print("getConnection")
		if connName in self._connections.keys():
			return self._connections[connName]
		else:
			return self._newConnection(
					connName,
					host=host,
					port=port,
					debug=debug,
					proxy=proxy,
					event_handler=event_handler
					)

	def _newConnection(
			self,
			connName,
			host,
			port,
			debug=False,
			proxy=None,
			event_handler=None
			):
		self._connections[connName] = SocketTransportClientFactory(host, port, debug=debug, proxy=proxy, event_handler=event_handler)
		return self._connections[connName]

	def bla(self):
		print("hello bla")
