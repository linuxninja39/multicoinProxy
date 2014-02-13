__author__ = 'melnichevv'

from stratum.socket_transport import SocketTransportClientFactory
from stratum import custom_exceptions

import stratum.logger
log = stratum.logger.get_logger('proxy')
class CustomSocketTransportClientFactory(SocketTransportClientFactory):
    # def __init__(self, host, port, allow_trusted=True, allow_untrusted=False,
    #              debug=False, signing_key=None, signing_id=None,
    #              is_reconnecting=True, proxy=None,
    #              event_handler=GenericEventHandler):
    #     super(CustomSocketTransportClientFactory, self).__init__(host, port, allow_trusted=True, allow_untrusted=False,
    #              debug=False, signing_key=None, signing_id=None,
    #              is_reconnecting=True, proxy=None,
    #              event_handler=GenericEventHandler)


    def rpc(self, method, params, *args, **kwargs):
        if not self.client:
            raise custom_exceptions.TransportException("Not connected")

        return self.client.rpc(method, params, *args, **kwargs)