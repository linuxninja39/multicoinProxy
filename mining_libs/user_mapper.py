# "url" : "stratum+tcp://elc.blocksolved.com:3304",
#                 "user" : "linuxninja39.1",
#                 "pass" : "x"
#
#                 "url"  : "stratum+tcp://pool.fcpool.com:3334",
#                 "user" : "linuxninja39.1",
#                 "pass" : "x"
#
#                 "url" : "stratum+tcp://stratum.give-me-ltc.com:3333",
#                 "user" : "linuxninja39.RaftusRig1LTC",
#                 "pass" : "x"
#
#                 "url" : "stratum+tcp://pool.luckycoinpool.com:3342",
#                 "user" : "linuxninja39.1",
#                 "pass" : "x"
#
#                 "url" : "stratum+tcp://stratum.khore.org:3334",
#                 "user" : "linuxninja39.1",
#                 "pass" : "x"
#
#                 "url" : "stratum+tcp://pool.d2.cc:3334",
#                 "user" : "linuxninja39.1",
#                 "pass" : "x"
#
#                 "url" : "stratum+tcp://pool.d2.cc:3335",
#                 "user" : "linuxninja39.1",
#                 "pass" : "x"

import stratum.logger
log = stratum.logger.get_logger('proxy')
class UserMapper():
    _userMap = {
        'linuxninja39_Blade8': {
            'password' : 'x',
            'workers' : {
                'elc.blocksolved.com:3304' : {
                    'remoteUsername': 'linuxninja39.1',
                    'remotePassword': 'x'
                },
                'pool.fcpool.com:3334' : {
                    'remoteUsername': 'linuxninja39.1',
                    'remotePassword': 'x'
                },
                'stratum.give-me-ltc.com:3333' : {
                    'remoteUsername': 'linuxninja39.RaftusRig1LTC',
                    'remotePassword': 'x'
                },
                'pool.luckycoinpool.com:3342' : {
                    'remoteUsername': 'linuxninja39.1',
                    'remotePassword': 'x'
                },
                'stratum.khore.org:3334' : {
                    'remoteUsername': 'linuxninja39.1',
                    'remotePassword': 'x'
                },
                'pool.d2.cc:3334' : {
                    'remoteUsername': 'linuxninja39.1',
                    'remotePassword': 'x'
                },
                'pool.d2.cc:3335' : {
                    'remoteUsername': 'linuxninja39.1',
                    'remotePassword': 'x'
                },
                'mint.bitminter.com:3333' : {
                    'remoteUsername': 'linuxninja39_Blade8',
                    'remotePassword': ''
                },
                'stratum.bitcoin.cz:3333' : {
                    'remoteUsername': 'melnichevv.worker1',
                    'remotePassword': 'SbvF3LLT'
                },
            }
        },
        'melnichevv': {
            'password': 'test',
            'workers' : {
                # 'stratum.bitcoin.cz:3333' : {
                #     'remoteUsername': 'melnichevv.worker1',
                #     'remotePassword': 'SbvF3LLT'
                # },
                'mint.bitminter.com:3333' : {
                    'remoteUsername': 'melnichevv_worker1',
                    'remotePassword': ''
                }
            }
        }
    }

    def getUser(self, username, password, host):
        if username in self._userMap:
            log.info('%s in username' % username)
            user = self._userMap[username]
            if user['password'] == password:
                log.info('%s:%s is ok' % (username, password))
                if host in user['workers']:
                    return user['workers'][host]
        else:
            return False;


    def getWorkerName(self, username, host):
        if username in self._userMap:
            user = self._userMap[username]
            if host in user['workers']:
                return user['workers'][host]['remoteUsername']
        else:
            return False;

