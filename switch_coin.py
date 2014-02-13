#!/usr/bin/env python2
__author__ = 'melnichevv'

import socket
import json
import argparse

def sw_parse_args():
    sw_parser = argparse.ArgumentParser(description='This program allows you to switch between coins manually.')
    sw_parser.add_argument('-o', '--host', dest='host', type=str, help='Hostname of Stratum mining pool')
    sw_parser.add_argument('-p', '--port', dest='port', type=int, help='Port of Stratum mining pool')
    return sw_parser.parse_args()

def main(args):
    data = {"method":"proxy.switch", "params": [args.host, args.port]}

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 50015))
    s.send(bytes(json.dumps(data)))
    s.close()

if __name__ == '__main__':
    sw_args = sw_parse_args()

    if not sw_args.host:
        print 'Host parameter is required'
    if not sw_args.port:
        print 'Port parameter is required'
    if sw_args.host and sw_args.port:
        main(sw_args)

    #TODO Add coin name parameter


