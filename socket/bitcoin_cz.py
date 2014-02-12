#!/usr/bin/env python2

import socket

HOST = '127.0.0.1'                 # Symbolic name meaning all available interfaces
PORT = 50013              # Arbitrary non-privileged port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) # Enable keepalive packets
s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 60) # Seconds before sending keepalive probes
s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 1) # Interval in seconds between keepalive probes
s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 5) # Failed keepalive probles before declaring other end dead
remote_pool = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
remote_pool.connect(('stratum.bitcoin.cz', 3333))
s.bind((HOST, PORT))
s.listen(10)
# print s.accept()
conn, addr = s.accept()
print 'Connected by', addr
while 1:
    data = conn.recv(2048)
    if data:
        print "Recieved from proxy:", data
        remote_pool.send(data)
    b_data = remote_pool.recv(2048)
    if b_data:
        print "Recieved from pool:", b_data
        conn.send(b_data)

#if not data: break
    #conn.sendall(data)
conn.close()