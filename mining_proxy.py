#!/usr/bin/env python2
'''
    Stratum mining proxy
    Copyright (C) 2012 Marek Palatinus <slush@satoshilabs.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import argparse
import time
import os
import socket
from twisted.internet import reactor, defer
from stratum.socket_transport import SocketTransportFactory
from stratum.services import ServiceEventHandler
from twisted.web.server import Site
import sys
from mining_libs.custom_classes import CustomSocketTransportClientFactory as SocketTransportClientFactory

from mining_libs import stratum_listener
from mining_libs import getwork_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import worker_registry
from mining_libs import multicast_responder
from mining_libs import version
from mining_libs import utils
from mining_libs.connection_pool import ConnectionPool

import stratum.logger
from mining_libs import database

def parse_args():  # https://www.btcguild.com/new_protocol.php
    parser = argparse.ArgumentParser(
        description='This proxy allows you to run getwork-based miners against Stratum mining pool.')
    # parser.add_argument('-o', '--host', dest='host', type=str, default='mint.bitminter.com',
    parser.add_argument('-o', '--host', dest='host', type=str, default='stratum.bitcoin.cz',
                        help='Hostname of Stratum mining pool')
    parser.add_argument('-p', '--port', dest='port', type=int, default=3333, help='Port of Stratum mining pool')
    # parser.add_argument('-o', '--host', dest='host', type=str, default='localhost', help='Hostname of Stratum mining pool')
    # parser.add_argument('-p', '--port', dest='port', type=int, default=50013, help='Port of Stratum mining pool')
    parser.add_argument('-sh', '--stratum-host', dest='stratum_host', type=str, default='0.0.0.0',
                        help='On which network interface listen for stratum miners. Use "localhost" for listening on internal IP only.')
    parser.add_argument('-sp', '--stratum-port', dest='stratum_port', type=int, default=3333,
                        help='Port on which port listen for stratum miners.')
    parser.add_argument('-oh', '--getwork-host', dest='getwork_host', type=str, default='0.0.0.0',
                        help='On which network interface listen for getwork miners. Use "localhost" for listening on internal IP only.')
    parser.add_argument('-gp', '--getwork-port', dest='getwork_port', type=int, default=8332,
                        help='Port on which port listen for getwork miners. Use another port if you have bitcoind RPC running on this machine already.')
    parser.add_argument('-nm', '--no-midstate', dest='no_midstate', action='store_true',
                        help="Don't compute midstate for getwork. This has outstanding performance boost, but some old miners like Diablo don't work without midstate.")
    parser.add_argument('-rt', '--real-target', dest='real_target', action='store_true',
                        help="Propagate >diff1 target to getwork miners. Some miners work incorrectly with higher difficulty.")
    parser.add_argument('-cl', '--custom-lp', dest='custom_lp', type=str,
                        help='Override URL provided in X-Long-Polling header')
    parser.add_argument('-cs', '--custom-stratum', dest='custom_stratum', type=str,
                        help='Override URL provided in X-Stratum header')
    parser.add_argument('-cu', '--custom-user', dest='custom_user', type=str,
                        help='Use this username for submitting shares')
    parser.add_argument('-cp', '--custom-password', dest='custom_password', type=str,
                        help='Use this password for submitting shares')
    parser.add_argument('--old-target', dest='old_target', action='store_true',
                        help='Provides backward compatible targets for some deprecated getwork miners.')
    parser.add_argument('--blocknotify', dest='blocknotify_cmd', type=str, default='',
                        help='Execute command when the best block changes (%%s in BLOCKNOTIFY_CMD is replaced by block hash)')
    parser.add_argument('--socks', dest='proxy', type=str, default='',
                        help='Use socks5 proxy for upstream Stratum connection, specify as host:port')
    parser.add_argument('--tor', dest='tor', action='store_true',
                        help='Configure proxy to mine over Tor (requires Tor running on local machine)')
    parser.add_argument('-t', '--test', dest='test', action='store_true', help='Run performance test on startup')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='Enable low-level debugging messages')
    parser.add_argument('-ns', '--no-switch', dest='no_switch', action='store_true', help='Disable switching mode.')
    parser.add_argument('-sw', '--switch-periodicity', dest='switch_periodicity', type=int, default=15,
                        help='Override default switch periodicity.')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='Make output more quiet')
    parser.add_argument('-i', '--pid-file', dest='pid_file', type=str, help='Store process pid to the file')
    parser.add_argument('-l', '--log-file', dest='log_file', type=str, help='Log to specified file')
    parser.add_argument('-st', '--scrypt-target', dest='scrypt_target', action='store_true', help='Calculate targets for scrypt algorithm')
    return parser.parse_args()

from stratum import settings

settings.LOGLEVEL = 'INFO'

if __name__ == '__main__':
    # We need to parse args & setup Stratum environment
    # before any other imports
    args = parse_args()
    if args.quiet:
        settings.DEBUG = False
        settings.LOGLEVEL = 'WARNING'
    elif args.verbose:
        settings.DEBUG = True
        settings.LOGLEVEL = 'DEBUG'
    if args.log_file:
        settings.LOGFILE = args.log_file

from twisted.internet import reactor, defer
from stratum.socket_transport import SocketTransportFactory, SocketTransportClientFactory
from stratum.services import ServiceEventHandler
from twisted.web.server import Site

from mining_libs import stratum_listener
from mining_libs import getwork_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import worker_registry
from mining_libs import multicast_responder
from mining_libs import version
from mining_libs import utils

import stratum.logger
log = stratum.logger.get_logger('proxy')


def on_shutdown(cp):
    '''Clean environment properly'''
    log.info("Shutting down proxy...")
    for conn_name in cp._connections:
        f = cp._connections[conn_name]
        f.is_reconnecting = False  # Don't let stratum factory to reconnect again


# @defer.inlineCallbacks
# def on_connect(f, workers, job_registry):
#     '''Callback when proxy get connected to the pool'''
#     log.info("Connected to Stratum pool at %s:%d" % f.main_host)
#     #reactor.callLater(30, f.client.transport.loseConnection)
#
#     # Hook to on_connect again
#     f.on_connect.addCallback(on_connect, workers, job_registry)
#
#     # Every worker have to re-autorize
#     workers.clear_authorizations()
#
#     if args.custom_user:
#         log.warning("Authorizing custom user %s, password %s" % (args.custom_user, args.custom_password))
#         workers.authorize(args.custom_user, args.custom_password)
#
#     # Subscribe for receiving jobs
#     log.info("Subscribing for mining jobs")
#     (_, extranonce1, extranonce2_size) = (yield f.rpc('mining.subscribe', []))[:3]
#     log.info (extranonce1)
#     log.info (extranonce2_size)
#     # job_registry.set_extranonce(extranonce1, extranonce2_size)
#     # stratum_listener.StratumProxyService._set_extranonce(extranonce1, extranonce2_size)
#     f.job_registry.set_extranonce(extranonce1, extranonce2_size)
#     stratum_listener.StratumProxyService._set_extranonce(f, extranonce1, extranonce2_size)
#
#     defer.returnValue(f)

@defer.inlineCallbacks
def new_on_connect(f):
    '''Callback when proxy get connected to the pool'''
    log.info("Connected to Stratum pool at %s:%d" % f.main_host)
    #reactor.callLater(30, f.client.transport.loseConnection)

    # Hook to on_connect again
    f.on_connect.addCallback(new_on_connect)

    # Every worker have to re-autorize
    f.workers.clear_authorizations()

    if args.custom_user:
        log.warning("Authorizing custom user %s, password %s" % (args.custom_user, args.custom_password))
        f.workers.authorize(args.custom_user, args.custom_password)

    # Subscribe for receiving jobs
    # log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    # log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    # log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    log.info("Subscribing for mining jobs on %s:%d" % (f.main_host[0], f.main_host[1]))
    (_, extranonce1, extranonce2_size) = (yield f.rpc('mining.subscribe', []))[:3]
    # log.info(extranonce1)
    # log.info(extranonce2_size)
    # job_registry.set_extranonce(extranonce1, extranonce2_size)
    # stratum_listener.StratumProxyService._set_extranonce(extranonce1, extranonce2_size)
    f.job_registry.set_extranonce(extranonce1, extranonce2_size)
    # log.info(f.extranonce1)
    # log.info(f.extranonce2_size)
    stratum_listener.StratumProxyService._set_extranonce(f, extranonce1, extranonce2_size)
    # log.info(f.extranonce1)
    # log.info(f.extranonce2_size)

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


@defer.inlineCallbacks
def new_on_disconnect(f):
    '''Callback when proxy get disconnected from the pool'''
    log.info("Disconnected from Stratum pool at %s:%d" % f.main_host)
    f.on_disconnect.addCallback(new_on_disconnect)

    # stratum_listener.MiningSubscription.disconnect_all()
    f.mining_subscription.disconnect_all()

    # Reject miners because we don't give a *job :-)
    f.workers.clear_authorizations()
    f.pool.close_connection(f.conn_name)
    return f


def test_launcher(result, job_registry):
    def run_test():
        log.info("Running performance self-test...")
        for m in (True, False):
            log.info("Generating with midstate: %s" % m)
            log.info("Example getwork:")
            log.info(job_registry.getwork(no_midstate=not m))

            start = time.time()
            n = 10000

            for x in range(n):
                job_registry.getwork(no_midstate=not m)

            log.info("%d getworks generated in %.03f sec, %d gw/s" % \
                     (n, time.time() - start, n / (time.time() - start)))

        log.info("Test done")

    reactor.callLater(1, run_test)
    return result


def print_deprecation_warning():
    '''Once new version is detected, this method prints deprecation warning every 30 seconds.'''

    log.warning("New proxy version available! Please update!")
    reactor.callLater(30, print_deprecation_warning)


def test_update():
    '''Perform lookup for newer proxy version, on startup and then once a day.
    When new version is found, it starts printing warning message and turned off next checks.'''

    GIT_URL = 'https://raw.github.com/slush0/stratum-mining-proxy/master/mining_libs/version.py'

    import urllib2

    log.warning("Checking for updates...")
    try:
        if version.VERSION not in urllib2.urlopen(GIT_URL).read():
            print_deprecation_warning()
            return  # New version already detected, stop periodic checks
    except:
        log.warning("Check failed.")

    reactor.callLater(3600 * 24, test_update)


def test():
    log.warning('test')
    reactor.callLater(5, test)


# def _oldswitch_proxy(f, periodicity, workers, job_registry, host, getwork):
#     # TODO Add Getting 'the best' coin
#     if host == 'mint.bitminter.com':
#         host = 'stratum.bitcoin.cz'
#     else:
#         host = 'mint.bitminter.com'
#     port = 3333
#     log.warning("-----------------------------------------------------------------------")
#     log.warning("--------------------------Switching To %s:%d---------------------------" % (host, port))
#     log.warning("-----------------------------------------------------------------------")
#
#     # job_registry = jobs.JobRegistry(self._f, cmd=jobs.JobRegistry.cmd, scrypt_target=jobs.JobRegistry.scrypt_target,
#     #                no_midstate=jobs.JobRegistry.no_midstate, real_target=jobs.JobRegistry.real_target, use_old_target=jobs.JobRegistry.old_target)
#
#     # job_registry = jobs.JobRegistry
#     # client_service.ClientMiningService.job_registry = job_registry
#     # client_service.ClientMiningService.reset_timeout()
#     #
#     # f = SocketTransportClientFactory('localhost', 50014,
#     #         debug=self._f.debug, proxy=self._f.proxy,
#     #         event_handler=client_service.ClientMiningService)
#     # workers = worker_registry.WorkerRegistry(f)
#     # log.info('Switch coin middle')
#     # self._f = f
#     # self._f.on_connect(workers, job_registry)
#     # log.info('-------------------------------')
#     # log.info('Reconnecting to localhost:50014')
#     # log.info('-------------------------------')
#     # self._f.reconnect('localhost', 50014, 60)
#     # reactor.listenMulticast(3333, multicast_responder.MulticastResponder(('localhost', 50014), 3333, 8332), listenMultiple=True)
#
#
#     # Setup multicast responder
#     # host = '127.0.0.1'
#     # port = 50014
#     # host = 'mint.bitminter.com'
#     # args.stratum_host = '0.0.0.0'
#     # args.stratum_port = 3333
#     # args.getwork_host = '0.0.0.0'
#     # args.getwork_port = 8332
#     #
#     # log.warning("Trying to connect to Stratum pool at %s:%d" % (host, port))
#     f.main_host = (host, port)
#     # f.port = port
#     # f.connect()
#     f.reconnect(host=host, port=port)
#     workers.set_host(host + ':' + str(port))
#     # f.retry()
#     # reactor.connectTCP(host, port, f)
#     # log.warning(workers.authorized)
#     # log.warning(workers.unauthorized)
#     # workers.clear_authorizations()
#     # f.on_connect.addCallback(on_connect, workers, job_registry)
#     # f.on_disconnect.addCallback(on_disconnect, workers, job_registry)
#     # f = SocketTransportClientFactory(args.host, args.port,
#     #            debug=args.verbose, proxy=args.proxy,
#     #            event_handler=client_service.ClientMiningSezrvice)
#     # f = SocketTransportClientFactory('127.0.0.1', 50014,
#     #            debug=args.verbose, proxy=args.proxy,
#     #            event_handler=client_service.ClientMiningService)
#     #
#     # job_registry = jobs.JobRegistry(
#     #         f,
#     #         cmd=args.blocknotify_cmd,
#     #         no_midstate=args.no_midstate,
#     #         real_target=args.real_target,
#     #         use_old_target=args.old_target
#     #         )
#     # client_service.ClientMiningService.job_registry = job_registry
#     # client_service.ClientMiningService.reset_timeout()
#     #
#     # workers = worker_registry.WorkerRegistry(f)
#     # f.on_connect.addCallback(on_connect, workers, job_registry)
#     # f.on_disconnect.addCallback(on_disconnect, workers, job_registry)
#     #
#     # if args.test:
#     #     f.on_connect.addCallback(test_launcher, job_registry)
#     #
#     # # Cleanup properly on shutdown
#     # reactor.addSystemEventTrigger('before', 'shutdown', on_shutdown, f)
#     #
#     # # Block until proxy connect to the pool
#     # yield f.on_connect
#     #
#     # # Setup stratum listener
#     # if args.stratum_port > 0:
#     #     stratum_listener.StratumProxyService._set_upstream_factory(f)
#     #     reactor.listenTCP(args.stratum_port, SocketTransportFactory(debug=False, event_handler=ServiceEventHandler))
#     #
#     # # Setup multicast responder
#     # # reactor.listenMulticast(3333, multicast_responder.MulticastResponder((args.host, args.port), args.stratum_port, args.getwork_port), listenMultiple=True)
#     # reactor.listenMulticast(3333, multicast_responder.MulticastResponder(('127.0.0.1', 50014), 3333, 8332), listenMultiple=True)
#     # '''
#     # log.warning("-----------------------------------------------------------------------")
#     # if args.getwork_host == '0.0.0.0' and args.stratum_host == '0.0.0.0':
#     #     log.warning("PROXY IS LISTENING ON ALL IPs ON PORT %d (stratum) AND %d (getwork)" % (args.stratum_port, args.getwork_port))
#     # else:
#     #     log.warning("LISTENING FOR MINERS ON http://%s:%d (getwork) and stratum+tcp://%s:%d (stratum)" % \
#     #              (args.getwork_host, args.getwork_port, args.stratum_host, args.stratum_port))
#     # log.warning("-----------------------------------------------------------------------")
#     # '''
#     reactor.callLater(periodicity, switch_proxy, f=f, workers=workers, job_registry=job_registry, host=host,
#                       periodicity=periodicity, getwork=getwork)


# def switch_proxy(cp, periodicity, switch=False):
#     if switch:
#         switch_users = database.get_list_of_switch_users()
#         """
#         id, host, port, username, password, proxy_username, profitability, `MAX(Coin.profitability)`, name
#         """
#         for user in switch_users:
#             if user['proxy_username'] in cp.users:
#                 cur_user = user
#                 f = cp.has_connection(cur_user['conn_name'])
#                 if f:
#                     conn_ref = cur_user['conn_ref']
#                     f.pubsub.unsubscribe(conn_ref, subscription=f.difficulty_subscription, key=cur_user['subs1'])
#                     f.pubsub.unsubscribe(conn_ref, subscription=f.mining_subscription, key=cur_user['subs2'])
#                     cur = f.users[conn_ref.get_ident()]
#                     users = {
#                         'proxyusername': cur['proxyusername'],
#                         'password': cur['password'],
#                         'pool_worker_username': user['worker_username'],
#                         'pool_worker_password': user['worker_password'],
#                         'conn_name': user['pool_id'],
#                         'tail': cur['tail'],
#                         'conn_ref': conn_ref,
#                         'subs1': cur['subs1'],
#                         'subs2': cur['subs1']
#                     }
#                     new_f = cp.has_connection(user['pool_id'])
#                     database.activate_user_worker(user['worker_username'], user['worker_password'], user['pool_id'])
#                     if not new_f:
#                         new_f = cp.get_connection(user['pool_id'])
#                         subs1 = new_f.pubsub.subscribe(conn_ref, new_f.difficulty_subscription, cur_user['subs1'])[0]
#                         subs2 = new_f.pubsub.subscribe(conn_ref, new_f.mining_subscription, cur_user['subs2'])[0]
#                         new_f.users[conn_ref.get_ident] = users
#                         new_f.difficulty_subscription.on_new_difficulty(new_f.difficulty_subscription.difficulty)  # Rework this, as this will affect all users
#                         # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
#                         new_f.job_registry.set_difficulty(new_f.difficulty_subscription.difficulty)
#                         result = (yield new_f.rpc('mining.authorize', [user['worker_username'], user['worker_password']]))
#             log.info('User %s was successfully switched from %s to %s pool!' % {user['proxy_username', str(f.main_host[0] + str(f.main_host[1])), str(new_f.main_host[0] + str(new_f.main_host[1]))] })
#     reactor.callLater(periodicity, switch_proxy, cp=cp, switch=True)


def switch_proxy(cp, periodicity, switch=False):
    # log.info("-----------------------------------------------------------------------")
    # # log.info("-----------------------------------------------------------------------")
    # # log.info("-------------------------------Switching-------------------------------")
    # log.info("-------------------------------Switching-------------------------------")
    # # log.info("-------------------------------Switching-------------------------------")
    # log.info("-----------------------------------------------------------------------")
    if switch == True:
        log.info("-----------------------------------------------------------------------")
        log.info("-------------------------------Switching-------------------------------")
        log.info("-----------------------------------------------------------------------")
        check_switch = database.check_switch()
        # log.info('switching process')
        # log.info('switching process')
        # log.info('switching process')
        # log.info('switching process')
        if check_switch:
            switch_users = database.get_list_of_switch_users()  # ToDo Rewrite SQL according to new database scheme
            log.info(switch_users)
            # for user in switch_users:
            #     log.info(user['pool_id'])
            #     log.info(user['proxy_username'])
            #     log.info(user['worker_username'])
            #     log.info(user['worker_password'])
            """
            pool_id, host, port,  worker_username, worker_password, proxy_username, etc
            """
            used = {}
            if len(switch_users) > 0:
                for user in switch_users:
                    # log.info(user)
                    # log.info('for method')
                    # log.info('cp.list_connections')
                    # log.info(cp.list_connections)
                    # log.info('cp.list_users')
                    # log.info(cp.list_users)
                    f = cp.get_pool_by_proxy_username(user['proxy_username'], True)
                    if f:
                        if user['proxy_username'] in cp.list_users[f.conn_name]:
                        # conn_name = cp.usernames[user['proxy_username']]['conn_name']
                        #     log.info('user in cp.users!')
                            # cur_user = cp.usernames[user['proxy_username']]
                            # log.info('cur_user')
                            # log.info(cur_user)
                            # log.info('IN "IF f" METHOD!')
                            # log.info(f.users)
                            # log.info(f.users.keys())
                            for conn_ref in cp.list_users[f.conn_name][user['proxy_username']]['connections']:
                                # log.info('f was found!')
                                # log.info(conn_ref)
                                usr = cp.list_connections.get(conn_ref, None)
                                if usr:
                                    cur = usr
                                    # log.info(cur)
                                    str_conn_ref = conn_ref
                                    conn_ref = cur['conn_ref']
                                    if conn_ref is not None:
                                        f.pubsub.unsubscribe(conn_ref, subscription=f.difficulty_subscription, key=cur['subs1'])
                                        f.pubsub.unsubscribe(conn_ref, subscription=f.mining_subscription, key=cur['subs2'])
                                        # for usr in switch_users:
                                        #     if usr['proxy_username'] != cur_user['proxyusername']:
                                        #         if cur_user['proxyusername'] in used:
                                        #             if cur_user['proxyusername'] != True:
                                        #                 new_user = usr
                                    #                 used[cur_user['proxyusername']] = True
                                    #         else:
                                    #             new_user = usr
                                    #             used[cur_user['proxyusername']] = True
                                    # new_user = cur
                                    new_user_info = {
                                        'subs1': cur['subs1'],
                                        'subs2': cur['subs1'],
                                        'tail': cur['tail'],
                                        'extranonce2_size': cur['extranonce2_size'],
                                        'proxy_username': user['proxy_username'],
                                        'proxy_password': user['proxy_password'],
                                        'pool_worker_username': user['worker_username'],
                                        'pool_worker_password': user['worker_password'],
                                        'pool_name': user['pool_id'],
                                        'conn_ref': conn_ref
                                    }
                                    # users = {
                                    #     'proxyusername': user['proxy_username'],
                                    #     'password': user['proxy_password'],
                                    #     'pool_worker_username': user['worker_username'],
                                    #     'pool_worker_password': user['worker_password'],
                                    #     'conn_name': user['pool_id'],
                                    #     'tail': cur['tail'],
                                    #     'conn_ref': conn_ref,
                                    #     'subs1': cur['subs1'],
                                    #     'subs2': cur['subs1']
                                    # }
                                    new_f = cp.has_connection(conn_name=user['pool_id'])
                                    if not new_f:
                                        new_f = cp.get_connection(conn_name=user['pool_id'], host=user['host'], port=user['port'])
                                    log.info('Switching user %s from %s to %s pool' % (str(user['proxy_username']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                    # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                    # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                    # database.activate_user(new_user['proxyusername'], new_user['conn_name'])
                                    database.deactivate_user_worker(user['worker_username'], user['worker_password'], f.conn_name)
                                    database.activate_user_worker(user['worker_username'], user['worker_password'], new_f.conn_name)
                                    if new_f.client == None or not new_f.client.connected:
                                        # f.new_users += [[user['worker_username'], user['worker_password']]]
                                        log.info('new_f.client == None')
                                    else:
                                        result = (new_f.rpc('mining.authorize', [user['worker_username'], user['worker_password']]))
                                    # log.info('after yield')
                                    # log.info('subscribing user %s on %s' % (str(conn_ref), new_f.conn_name))
                                    # log.info('subscribing user %s on %s' % (str(conn_ref), new_f.conn_name))
                                    # log.info('subscribing user %s on %s' % (str(conn_ref), new_f.conn_name))
                                    # log.info('subscribing user %s on %s' % (str(conn_ref), new_f.conn_name))
                                    # log.info('subscribing user %s on %s' % (str(conn_ref), new_f.conn_name))
                                    subs1 = new_f.pubsub.subscribe(conn_ref, new_f.difficulty_subscription, cur['subs1'])[0]
                                    subs2 = new_f.pubsub.subscribe(conn_ref, new_f.mining_subscription, cur['subs2'])[0]
                                    # new_f.users[conn_ref.get_ident()] = users
                                    cp.list_connections[str_conn_ref] = new_user_info  # Move this
                                    # log.info('cp.list_connections')
                                    # log.info(cp.list_connections)
                                    # log.info('cp.list_users')
                                    # log.info(cp.list_users)
                                    new_f.difficulty_subscription.emit_single(new_f.difficulty_subscription.difficulty, f=new_f)
                                    # # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
                                    log.info('User %s was successfully switched from %s to %s pool' % (str(user['proxy_username']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                    # log.info(f.cp.list_users)
                                    q = f.cp.list_users[f.conn_name].pop(user['proxy_username'], None)
                                    # log.info(q)
                                    # log.info(f.cp.list_users)
                                    # uindex = f.usernames[user['proxy_username']]['connections'].index(usr)
                                    # f.usernames[user['proxy_username']]['connections'] = f.usernames[user['proxy_username']]['connections'][:uindex] + f.usernames[user['proxy_username']]['connections'][uindex+1:]
                                    if user['proxy_username'] not in cp.list_users[new_f.conn_name]:
                                        cp.list_users[new_f.conn_name][user['proxy_username']] = cp.list_connections[str_conn_ref]
                                        if 'connections' not in cp.list_users[new_f.conn_name][user['proxy_username']]:
                                            cp.list_users[new_f.conn_name][user['proxy_username']].update({'connections':  []})
                                            cp.list_users[new_f.conn_name][user['proxy_username']]['connections'] += [str_conn_ref]
                                    # log.info(f.cp.list_users)
                                    # if user['proxy_username'] not in new_f.usernames.keys():
                                    #     new_f.usernames[user['proxy_username']] = {}
                                    # if 'connections' not in new_f.usernames[user['proxy_username']]:
                                    #     new_f.usernames[user['proxy_username']]['connections'] = []
                                       # f.usernames[user['proxy_username']]['connections']
                                    # log.info('------------------------------------------')
                                    # log.info(conn_ref.get_ident())
                                    # log.info('was added to %s pool' % str(new_f.conn_name))
                                    # log.info('------------------------------------------')
                                    # # new_f.usernames[user['proxy_username']]['connections'] += [conn_ref.get_ident(), ]
                                    # log.info(new_f.users)
                                    # log.info(new_f.usernames)
                                    # log.info('------------------------------------------')
                                    # if new_f.client == None or not new_f.client.connected:
                                    #     yield f.on_connect()
                                # else:
                                #     cur = f.users[usr]
                                #     log.info(cur)
                                #     conn_ref = cur['conn_ref']
                                #     f.pubsub.unsubscribe(conn_ref, subscription=f.difficulty_subscription, key=cur['subs1'])
                                #     f.pubsub.unsubscribe(conn_ref, subscription=f.mining_subscription, key=cur['subs2'])
                                #     # for usr in switch_users:
                                #     #     if usr['proxy_username'] != cur_user['proxyusername']:
                                #     #         if cur_user['proxyusername'] in used:
                                #     #             if cur_user['proxyusername'] != True:
                                #     #                 new_user = usr
                                #     #                 used[cur_user['proxyusername']] = True
                                #     #         else:
                                #     #             new_user = usr
                                #     #             used[cur_user['proxyusername']] = True
                                #     # new_user = cur
                                #     users = {
                                #         'proxyusername': cur['proxyusername'],
                                #         'password': cur['password'],
                                #         'pool_worker_username': user['worker_username'],
                                #         'pool_worker_password': user['worker_password'],
                                #         'conn_name': user['pool_id'],
                                #         'tail': cur['tail'],
                                #         'conn_ref': conn_ref,
                                #         'subs1': cur['subs1'],
                                #         'subs2': cur['subs1']
                                #     }
                                #     new_f = cp.has_connection(conn_name=user['pool_id'])
                                #     if not new_f:
                                #         new_f = cp.get_connection(conn_name=user['pool_id'], host=user['host'], port=user['port'])
                                #     log.info('Switching user %s from %s to %s pool' % (str(cur['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                #     # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                #     # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                #     # database.activate_user(new_user['proxyusername'], new_user['conn_name'])
                                #     database.deactivate_user_worker(user['worker_username'], user['worker_password'], f.conn_name)
                                #     database.activate_user_worker(user['worker_username'], user['worker_password'], new_f.conn_name)
                                #     if new_f.client == None or not new_f.client.connected:
                                #         f.new_users += [[user['worker_username'], user['worker_password']]]
                                #     else:
                                #         result = (new_f.rpc('mining.authorize', [user['worker_username'], user['worker_password']]))
                                #     log.info('after yield')
                                #     subs1 = new_f.pubsub.subscribe(conn_ref, new_f.difficulty_subscription, cur['subs1'])[0]
                                #     subs2 = new_f.pubsub.subscribe(conn_ref, new_f.mining_subscription, cur['subs2'])[0]
                                #     new_f.users[conn_ref.get_ident()] = users
                                #     new_f.cp[new_f.conn_name].connection_users[conn_ref.get_ident()] = users
                                #     new_f.difficulty_subscription.emit_single(new_f.difficulty_subscription.difficulty, f=new_f)
                                #     # # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
                                #     log.info('User %s was successfully switched from %s to %s pool' % (str(cur['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                #     f.users.pop(conn_ref.get_ident(), None)
                                #     uindex = f.usernames[user['proxy_username']]['connections'].index(usr)
                                #     f.usernames[user['proxy_username']]['connections'] = f.usernames[user['proxy_username']]['connections'][:uindex] + f.usernames[user['proxy_username']]['connections'][uindex+1:]
                                #     if user['proxy_username'] not in new_f.usernames.keys():
                                #         new_f.usernames[user['proxy_username']] = {}
                                #     if 'connections' not in new_f.usernames[user['proxy_username']]:
                                #         new_f.usernames[user['proxy_username']]['connections'] = []
                                #        # f.usernames[user['proxy_username']]['connections']
                                #     log.info('------------------------------------------')
                                #     log.info(conn_ref.get_ident())
                                #     log.info('was added to %s pool' % str(new_f.conn_name))
                                #     log.info('------------------------------------------')
                                #     new_f.usernames[user['proxy_username']]['connections'] += [conn_ref.get_ident(), ]
                                #     log.info(new_f.users)
                                #     log.info(new_f.usernames)
                                #     log.info('------------------------------------------')
                                #     # if new_f.client == None or not new_f.client.connected:
                                #     #     yield f.on_connect()
                                    q = 1
                                    # f.users.pop(usr)
                                else:
                                    cp.list_connections.pop(str_conn_ref)
                                    cp.list_users[f.conn_name][user['proxy_username']]['connections'].pop(str_conn_ref)
                                    # log.info("remove connection, as it's outdated")
        else:
            log.info("-----------------------------------------------------------------------")
            log.info("---------------------------Nothing to switch---------------------------")
            log.info("-----------------------------------------------------------------------")
    switch = True
    reactor.callLater(periodicity, switch_proxy, cp=cp, switch=switch, periodicity=periodicity)

def new_old_switch_proxy(cp, periodicity, switch=False):
    log.info("-----------------------------------------------------------------------")
    # log.info("-----------------------------------------------------------------------")
    # log.info("-------------------------------Switching-------------------------------")
    log.info("-------------------------------Switching-------------------------------")
    # log.info("-------------------------------Switching-------------------------------")
    log.info("-----------------------------------------------------------------------")
    if switch == True:
        log.info("-----------------------------------------------------------------------")
        # log.info("-----------------------------------------------------------------------")
        # log.info("-------------------------------Switching-------------------------------")
        log.info("-------------------------------Switching-------------------------------")
        # log.info("-------------------------------Switching-------------------------------")
        log.info("-----------------------------------------------------------------------")
        # log.info("-----------------------------------------------------------------------")
        # log.info('switching process')
        # log.info('switching process')
        # log.info('switching process')
        # log.info('switching process')
        switch_users = database.get_list_of_switch_users()  # ToDo Rewrite SQL according to new database scheme
        log.info(switch_users)
        # for user in switch_users:
        #     log.info(user['pool_id'])
        #     log.info(user['proxy_username'])
        #     log.info(user['worker_username'])
        #     log.info(user['worker_password'])
        """
        pool_id, host, port,  worker_username, worker_password, proxy_username, etc
        """
        used = {}
        if len(switch_users) > 0:
            for user in switch_users:
                log.info(user)
                log.info('for method')
                f = cp.get_connection(conn_name=user['pool_id'])
                if user['proxy_username'] in cp.list_users:
                    conn_name = cp.usernames[user['proxy_username']]['conn_name']
                    log.info('user in cp.users!')
                    cur_user = cp.usernames[user['proxy_username']]
                    log.info('cur_user')
                    log.info(cur_user)
                    if f:
                        log.info('IN "IF f" METHOD!')
                        log.info(f.users)
                        log.info(f.users.keys())
                        for usr in f.usernames[user['proxy_username']]['connections']:
                            log.info('f was found!')
                            log.info(usr)
                            if usr in f.users:
                                cur = f.users[usr]
                                log.info(cur)
                                conn_ref = cur['conn_ref']
                                f.pubsub.unsubscribe(conn_ref, subscription=f.difficulty_subscription, key=cur['subs1'])
                                f.pubsub.unsubscribe(conn_ref, subscription=f.mining_subscription, key=cur['subs2'])
                                # for usr in switch_users:
                                #     if usr['proxy_username'] != cur_user['proxyusername']:
                                #         if cur_user['proxyusername'] in used:
                                #             if cur_user['proxyusername'] != True:
                                #                 new_user = usr
                                #                 used[cur_user['proxyusername']] = True
                                #         else:
                                #             new_user = usr
                                #             used[cur_user['proxyusername']] = True
                                # new_user = cur
                                users = {
                                    'proxyusername': user['proxy_username'],
                                    'password': user['proxy_password'],
                                    'pool_worker_username': user['worker_username'],
                                    'pool_worker_password': user['worker_password'],
                                    'conn_name': user['pool_id'],
                                    'tail': cur['tail'],
                                    'conn_ref': conn_ref,
                                    'subs1': cur['subs1'],
                                    'subs2': cur['subs1']
                                }
                                new_f = cp.has_connection(conn_name=user['pool_id'])
                                if not new_f:
                                    new_f = cp.get_connection(conn_name=user['pool_id'], host=user['host'], port=user['port'])
                                log.info('Switching user %s from %s to %s pool' % (str(cur['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                # database.activate_user(new_user['proxyusername'], new_user['conn_name'])
                                database.deactivate_user_worker(user['worker_username'], user['worker_password'], f.conn_name)
                                database.activate_user_worker(user['worker_username'], user['worker_password'], new_f.conn_name)
                                if new_f.client == None or not new_f.client.connected:
                                    f.new_users += [[user['worker_username'], user['worker_password']]]
                                else:
                                    result = (new_f.rpc('mining.authorize', [user['worker_username'], user['worker_password']]))
                                log.info('after yield')
                                subs1 = new_f.pubsub.subscribe(conn_ref, new_f.difficulty_subscription, cur['subs1'])[0]
                                subs2 = new_f.pubsub.subscribe(conn_ref, new_f.mining_subscription, cur['subs2'])[0]
                                new_f.users[conn_ref.get_ident()] = users
                                new_f.difficulty_subscription.emit_single(new_f.difficulty_subscription.difficulty, f=new_f)
                                # # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
                                log.info('User %s was successfully switched from %s to %s pool' % (str(cur['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                                f.cp.connection_users[f.conn_name].pop(conn_ref.get_ident(), None)
                                f.users.pop(conn_ref.get_ident(), None)
                                uindex = f.usernames[user['proxy_username']]['connections'].index(usr)
                                f.usernames[user['proxy_username']]['connections'] = f.usernames[user['proxy_username']]['connections'][:uindex] + f.usernames[user['proxy_username']]['connections'][uindex+1:]
                                if user['proxy_username'] not in new_f.usernames.keys():
                                    new_f.usernames[user['proxy_username']] = {}
                                if 'connections' not in new_f.usernames[user['proxy_username']]:
                                    new_f.usernames[user['proxy_username']]['connections'] = []
                                   # f.usernames[user['proxy_username']]['connections']
                                log.info('------------------------------------------')
                                log.info(conn_ref.get_ident())
                                log.info('was added to %s pool' % str(new_f.conn_name))
                                log.info('------------------------------------------')
                                new_f.usernames[user['proxy_username']]['connections'] += [conn_ref.get_ident(), ]
                                log.info(new_f.users)
                                log.info(new_f.usernames)
                                log.info('------------------------------------------')
                                # if new_f.client == None or not new_f.client.connected:
                                #     yield f.on_connect()
                            # else:
                            #     cur = f.users[usr]
                            #     log.info(cur)
                            #     conn_ref = cur['conn_ref']
                            #     f.pubsub.unsubscribe(conn_ref, subscription=f.difficulty_subscription, key=cur['subs1'])
                            #     f.pubsub.unsubscribe(conn_ref, subscription=f.mining_subscription, key=cur['subs2'])
                            #     # for usr in switch_users:
                            #     #     if usr['proxy_username'] != cur_user['proxyusername']:
                            #     #         if cur_user['proxyusername'] in used:
                            #     #             if cur_user['proxyusername'] != True:
                            #     #                 new_user = usr
                            #     #                 used[cur_user['proxyusername']] = True
                            #     #         else:
                            #     #             new_user = usr
                            #     #             used[cur_user['proxyusername']] = True
                            #     # new_user = cur
                            #     users = {
                            #         'proxyusername': cur['proxyusername'],
                            #         'password': cur['password'],
                            #         'pool_worker_username': user['worker_username'],
                            #         'pool_worker_password': user['worker_password'],
                            #         'conn_name': user['pool_id'],
                            #         'tail': cur['tail'],
                            #         'conn_ref': conn_ref,
                            #         'subs1': cur['subs1'],
                            #         'subs2': cur['subs1']
                            #     }
                            #     new_f = cp.has_connection(conn_name=user['pool_id'])
                            #     if not new_f:
                            #         new_f = cp.get_connection(conn_name=user['pool_id'], host=user['host'], port=user['port'])
                            #     log.info('Switching user %s from %s to %s pool' % (str(cur['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                            #     # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                            #     # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                            #     # database.activate_user(new_user['proxyusername'], new_user['conn_name'])
                            #     database.deactivate_user_worker(user['worker_username'], user['worker_password'], f.conn_name)
                            #     database.activate_user_worker(user['worker_username'], user['worker_password'], new_f.conn_name)
                            #     if new_f.client == None or not new_f.client.connected:
                            #         f.new_users += [[user['worker_username'], user['worker_password']]]
                            #     else:
                            #         result = (new_f.rpc('mining.authorize', [user['worker_username'], user['worker_password']]))
                            #     log.info('after yield')
                            #     subs1 = new_f.pubsub.subscribe(conn_ref, new_f.difficulty_subscription, cur['subs1'])[0]
                            #     subs2 = new_f.pubsub.subscribe(conn_ref, new_f.mining_subscription, cur['subs2'])[0]
                            #     new_f.users[conn_ref.get_ident()] = users
                            #     new_f.cp[new_f.conn_name].connection_users[conn_ref.get_ident()] = users
                            #     new_f.difficulty_subscription.emit_single(new_f.difficulty_subscription.difficulty, f=new_f)
                            #     # # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
                            #     log.info('User %s was successfully switched from %s to %s pool' % (str(cur['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                            #     f.users.pop(conn_ref.get_ident(), None)
                            #     uindex = f.usernames[user['proxy_username']]['connections'].index(usr)
                            #     f.usernames[user['proxy_username']]['connections'] = f.usernames[user['proxy_username']]['connections'][:uindex] + f.usernames[user['proxy_username']]['connections'][uindex+1:]
                            #     if user['proxy_username'] not in new_f.usernames.keys():
                            #         new_f.usernames[user['proxy_username']] = {}
                            #     if 'connections' not in new_f.usernames[user['proxy_username']]:
                            #         new_f.usernames[user['proxy_username']]['connections'] = []
                            #        # f.usernames[user['proxy_username']]['connections']
                            #     log.info('------------------------------------------')
                            #     log.info(conn_ref.get_ident())
                            #     log.info('was added to %s pool' % str(new_f.conn_name))
                            #     log.info('------------------------------------------')
                            #     new_f.usernames[user['proxy_username']]['connections'] += [conn_ref.get_ident(), ]
                            #     log.info(new_f.users)
                            #     log.info(new_f.usernames)
                            #     log.info('------------------------------------------')
                            #     # if new_f.client == None or not new_f.client.connected:
                            #     #     yield f.on_connect()
                                q = 1
                                # f.users.pop(usr)
                                log.info("remove connection, as it's outdated")
    switch = True
    reactor.callLater(periodicity, switch_proxy, cp=cp, switch=switch, periodicity=periodicity)


def test_switch_proxy(cp, periodicity, switch=False):
    if switch == True:
        log.info("-----------------------------------------------------------------------")
        # log.info("-----------------------------------------------------------------------")
        # log.info("-------------------------------Switching-------------------------------")
        log.info("-------------------------------Switching-------------------------------")
        # log.info("-------------------------------Switching-------------------------------")
        log.info("-----------------------------------------------------------------------")
        # log.info("-----------------------------------------------------------------------")
        # log.info('switching process')
        # log.info('switching process')
        # log.info('switching process')
        # log.info('switching process')
        switch_users = database.get_list_of_active_users()
        # for user in switch_users:
        #     log.info(user['pool_id'])
        #     log.info(user['proxy_username'])
        #     log.info(user['worker_username'])
        #     log.info(user['worker_password'])
        """
        pool_id, worker_username, worker_password, proxy_username
        """
        used = {}
        if len(switch_users) > 1:
            for user in switch_users:
                # log.info(user)
                # log.info('for method')
                if user['proxy_username'] in cp.usernames:
                    # log.info('user in cp.users!')
                    cur_user = cp.usernames[user['proxy_username']]
                    # log.info('cur_user')
                    # log.info(cur_user)
                    f = cp.has_connection(cur_user['conn_name'])
                    if f:
                        log.info('f was found!')
                        conn_ref = cur_user['conn_ref']
                        f.pubsub.unsubscribe(conn_ref, subscription=f.difficulty_subscription, key=cur_user['subs1'])
                        f.pubsub.unsubscribe(conn_ref, subscription=f.mining_subscription, key=cur_user['subs2'])
                        cur = f.users[conn_ref.get_ident()]
                        for usr in switch_users:
                            if usr['proxy_username'] != cur_user['proxyusername']:
                                if cur_user['proxyusername'] in used:
                                    if cur_user['proxyusername'] != True:
                                        new_user = usr
                                        used[cur_user['proxyusername']] = True
                                else:
                                    new_user = usr
                                    used[cur_user['proxyusername']] = True
                        users = {
                            'proxyusername': cur['proxyusername'],
                            'password': cur['password'],
                            'pool_worker_username': new_user['worker_username'],
                            'pool_worker_password': new_user['worker_password'],
                            'conn_name': new_user['pool_id'],
                            'tail': cur['tail'],
                            'conn_ref': conn_ref,
                            'subs1': cur['subs1'],
                            'subs2': cur['subs1']
                        }
                        new_f = cp.has_connection(new_user['pool_id'])
                        log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                        # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                        # log.info('Switching user %s from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                        database.activate_user_worker(new_user['worker_username'], new_user['worker_password'], new_user['pool_id'])  # ToDo Rewrite SQL according to new database scheme
                        if not new_f:
                            new_f = cp.get_connection(new_user['pool_id'])
                        subs1 = new_f.pubsub.subscribe(conn_ref, new_f.difficulty_subscription, cur['subs1'])[0]
                        subs2 = new_f.pubsub.subscribe(conn_ref, new_f.mining_subscription, cur['subs2'])[0]
                        new_f.users[conn_ref.get_ident()] = users
                        new_f.cp.connection_user[new_f.conn_name][conn_ref.get_ident()] = users
                        new_f.difficulty_subscription.on_new_difficulty(new_f.difficulty_subscription.difficulty)  # Rework this, as this will affect all users
                        # # stratum_listener.DifficultySubscription.on_new_difficulty(difficulty)
                        new_f.job_registry.set_difficulty(new_f.difficulty_subscription.difficulty)
                        result = (new_f.rpc('mining.authorize', [new_user['worker_username'], new_user['worker_password']]))
                        log.info('User %s was successfully switched from %s to %s pool' % (str(cur_user['proxyusername']), str(str(f.main_host[0]) + ':' + str(f.main_host[1])), str(str(new_f.main_host[0]) + ':' + str(new_f.main_host[1]))))
                        f.cp.connection_users[f.conn_name].pop(conn_ref.get_ident(), None)
                        f.users.pop(conn_ref.get_ident(), None)
                        f.cp.connection_user[f.conn_name].pop(conn_ref.get_ident())
        switch = False
    else:
        switch = True
    reactor.callLater(periodicity, test_switch_proxy, cp=cp, switch=switch, periodicity=periodicity)

def restart_program():
    """Restarts the current program.
    Note: this function does not return. Any cleanup action (like
    saving data) must be done before calling this function."""
    python = sys.executable
    os.execl(python, python, * sys.argv)

@defer.inlineCallbacks
def main(args):
    if args.pid_file:
        fp = file(args.pid_file, 'w')
        fp.write(str(os.getpid()))
        fp.close()

    if args.port != 3333:
        '''User most likely provided host/port
        for getwork interface. Let's try to detect
        Stratum host/port of given getwork pool.'''

        try:
            new_host = (yield utils.detect_stratum(args.host, args.port))
        except:
            log.exception("Stratum host/port autodetection failed")
            new_host = None

        if new_host != None:
            args.host = new_host[0]
            args.port = new_host[1]

    log.warning("Stratum proxy version: %s" % version.VERSION)
    # Setup periodic checks for a new version
    # test_update()

    if args.tor:
        log.warning("Configuring Tor connection")
        args.proxy = '127.0.0.1:9050'
        args.host = 'pool57wkuu5yuhzb.onion'
        args.port = 3333

    if args.proxy:
        proxy = args.proxy.split(':')
        if len(proxy) < 2:
            proxy = (proxy, 9050)
        else:
            proxy = (proxy[0], int(proxy[1]))
        log.warning("Using proxy %s:%d" % proxy)
    else:
        proxy = None

    log.warning("Trying to connect to Stratum pool at %s:%d" % (args.host, args.port))

    cp = ConnectionPool(debug=args.verbose,
                        # proxy=proxy,
                        # event_handler=client_service.ClientMiningService,
                        cmd=args.blocknotify_cmd,
                        no_midstate=args.no_midstate,
                        real_target=args.real_target,
                        use_old_target=args.old_target,
                        scrypt_target=args.scrypt_target,
    )
    client_service.ClientMiningService.set_cp(cp)
    # Connect to Stratum pool
    log.info(args.host + ':' + str(args.port))
    database.deactivate_all_users()  # ToDo Rewrite SQL according to new database scheme
    # cp.init_all_pools()
    cp.init_one_pool()
    # f = cp.get_connection(host=args.host, port=args.port)
    # log.info(f)
    # f = SocketTransportClientFactory(args.host, args.port,
    #                                  debug=args.verbose, proxy=proxy,
    #                                  event_handler=client_service.ClientMiningService)
    # client_service.ClientMiningService.set_cp(f)
    # f = cp.getConnection(
    #         'default',
    #         host=args.host,
    #         port=args.port,
    #         debug=args.verbose,
    #         proxy=proxy,
    #         event_handler=client_service.ClientMiningService
    #         )
    # f1 = cp.getConnection(
    #         'additional',
    #         host='127.0.0.1',
    #         port='50014',
    #         debug=args.verbose,
    #         proxy=proxy,
    #         event_handler=client_service.ClientMiningService
    #         )
    # test()

    # job_registry = jobs.JobRegistry(
    #     f,
    #     cmd=args.blocknotify_cmd,
    #     no_midstate=args.no_midstate,
    #     real_target=args.real_target,
    #     use_old_target=args.old_target
    # )
    # job_registry = f.job_registry
    # cp.job_registry = job_registry
    # client_service.ClientMiningService.job_registry = job_registry
    # client_service.ClientMiningService.reset_timeout()

    # workers = worker_registry.WorkerRegistry(cp)

    # f.on_connect.addCallback(on_connect, workers, job_registry)
    # f.on_disconnect.addCallback(on_disconnect, workers, job_registry)
    # cp.on_connect_callback = new_on_connect
    # cp.on_disconnect_callback = new_on_disconnect
    # workers.set_host(args.host, args.port)

    if args.test:
        f.on_connect.addCallback(test_launcher, job_registry)

    # Cleanup properly on shutdown
    # reactor.addSystemEventTrigger('before', 'shutdown', on_shutdown, f)
    reactor.addSystemEventTrigger('before', 'shutdown', on_shutdown, cp=cp)

    # Block until proxy connect to the pool
    # yield f.on_connect  # Temporarily commented out

    # # Setup getwork listener
    # getwork_lstnr = None
    # if args.getwork_port > 0:
    #     getwork_lstnr = getwork_listener.Root(job_registry, workers,
    #                                           stratum_host=args.stratum_host, stratum_port=args.stratum_port,
    #                                           custom_lp=args.custom_lp, custom_stratum=args.custom_stratum,
    #                                           custom_user=args.custom_user, custom_password=args.custom_password)
    #     getwork_lstnr.set_host(args.host + ':' + str(args.port))
    #     conn = reactor.listenTCP(args.getwork_port, Site(getwork_lstnr),
    #                              interface=args.getwork_host)
    #
    #     try:
    #         conn.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Enable keepalive packets
    #         conn.socket.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 60)  # Seconds before sending keepalive probes
    #         conn.socket.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL,
    #                                1)  # Interval in seconds between keepalive probes
    #         conn.socket.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT,
    #                                5)  # Failed keepalive probles before declaring other end dead
    #     except:
    #         pass  # Some socket features are not available on all platforms (you can guess which one)

    # Setup stratum listener
    if args.stratum_port > 0:
        stratum_listener.StratumProxyService._set_upstream_factory(cp)
        reactor.listenTCP(args.stratum_port, SocketTransportFactory(debug=False, event_handler=ServiceEventHandler))

    # Setup multicast responder
    reactor.listenMulticast(3333, multicast_responder.MulticastResponder((args.host, args.port), args.stratum_port,
                                                                         args.getwork_port), listenMultiple=True)

    log.warning("-----------------------------------------------------------------------")
    if args.getwork_host == '0.0.0.0' and args.stratum_host == '0.0.0.0':
        log.warning("PROXY IS LISTENING ON ALL IPs ON PORT %d (stratum) AND %d (getwork)" % (
            args.stratum_port, args.getwork_port))
    else:
        log.warning("LISTENING FOR MINERS ON http://%s:%d (getwork) and stratum+tcp://%s:%d (stratum)" % \
                    (args.getwork_host, args.getwork_port, args.stratum_host, args.stratum_port))
    log.warning("-----------------------------------------------------------------------")
    if not args.no_switch:
        log.warning("-----------------------Proxy Switching Scheduled-----------------------")
        log.warning("----------------Switch Periodicity is set to %d seconds----------------" % args.switch_periodicity)
        log.warning("-----------------------------------------------------------------------")
        switch_proxy(cp, args.switch_periodicity, False)
        # reactor.callLater(args.switch_periodicity, test_switch_proxy, cp=cp, periodicity=args.switch_periodicity, switch=True)
    reactor.callLater(1800, restart_program)


if __name__ == '__main__':
    main(args)
    reactor.run()

'''
The Main Idea:
Now we are using one instance of StratumProxyService (class for user authorization/subscribing/job submitting) only,
such as MiningSubscription(_ms) and DifficultySubscription(_ds). You can find them in mining_libs/stratum_listener.py
Also we are using one instance of SocketTransportClientFactory (_f).
New pool's information is mostly stored in _f, so the idea is to put both _ms and _ds to _f and information about jobs & workers too.
From the other side, list of _f will be stored in mining_libs/connection_pool.py. We will check for every
authorize/subscribe/submit event to get current _f for current user.
Also, we are using one instance of both WorkerRegistry and JobRegistry too.
The idea is to store all information in _f, so we can get everything, we need, on any step in any time.

For now I don't know, how defer.inlineCallbacks will work with multiple _f, as it will have multiple identical callbacks.
Maybe it will be needed to create multiple defer objects, but in this case, it will be better(easier?) to use multithreading.

All listed ideas and ToDos are applicable for stratum protocol only. After finishing these changes to this, I can make them
to getwork protocol too.

To Do List:
1). mining_proxy.py:
    - overwrite on_connect method
    - overwrite on_disconnect method
    - rework main function
    -
2). mining_libs/client_service.py:
    #This file contains class CustomStratumProxyService extended from StratumProxyService, so
    #here will be main changes, described above.
    - overwrite __init__ method
    - add mining & difficulty subscriptions
    - add list of jobs and workers
    - add extranonces/tails from StratumProxyService

3). mining_libs/stratum_listener.py:
    a). DifficultySubscription
        - move to CustomSocketClientTransportFactory
    b). MiningSubscription
        - move to CustomSocketClientTransportFactory
    3). StratumProxyService
        - move extranonces, tails to CustomSocketClientTransportFactory
        - rewrite get/set method to user values from CustomSocketClientTransportFactory
        - rewrite authorize/subscribe methods

4). mining_libs/worker_registry.py
    - rewrite all methods to use current user's CustomSocketClientTransportFactory
    - move main variables to CustomSocketClientTransportFactory

5). mining_libs/jobs.py
    - rewrite all methods to use current user's CustomSocketClientTransportFactory
    - move main variables to CustomSocketClientTransportFactory

'''
