#!/usr/bin/env python2

import socket
import json
import urllib2

HOST = '127.0.0.1'                 # Symbolic name meaning all available interfaces
PORT = 50014              # Arbitrary non-privileged port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) # Enable keepalive packets
s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 60) # Seconds before sending keepalive probes
s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 1) # Interval in seconds between keepalive probes
s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 5) # Failed keepalive probles before declaring other end dead
remote_pool = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
remote_pool.connect(('mint.bitminter.com', 3333))
s.bind((HOST, PORT))
s.listen(10)
# print s.accept()
while 1:
    conn, addr = s.accept()
    print 'Connected by', addr
    data = conn.recv(2048)
    if data:
        try:
            ret = json.loads(data)
            print ret
            print ret['method']
            print ret['params']
            if 'method' in ret and 'params' in ret:
                # print 'method:', ret['method']
                if ret['method'] == 'proxy.switch':
                #     print 'params:', ret['params']
                    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    proxy.connect(('127.0.0.1', 3333))
                    proxy.send(data)
                    proxy.close()
        except Exception:
            print "Something went wrong"
        print "Received from proxy:", ret
        remote_pool.send(data)
    b_data = remote_pool.recv(2048)
    if b_data:
        print "Received from pool:", b_data
        conn.send(b_data)

#if not data: break
    #conn.sendall(data)
remote_pool.close()
conn.close()