#!/usr/bin/env python2

import socket

HOST = '127.0.0.1'                 # Symbolic name meaning all available interfaces
PORT = 50014              # Arbitrary non-privileged port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
bitcoin = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
bitcoin.connect(('mint.bitminter.com', 3333))
s.bind((HOST, PORT))
s.listen(10)
# print s.accept()
conn, addr = s.accept()
print 'Connected by', addr
while 1:
    data = conn.recv(2048)
    if data:
        print "Recieved from proxy:", data
        bitcoin.send(data)
    b_data = bitcoin.recv(2048)
    if b_data:
        print "Recieved from pool:", b_data
        conn.send(b_data)

#if not data: break
    #conn.sendall(data)
conn.close()
