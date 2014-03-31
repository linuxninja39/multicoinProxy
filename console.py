#!/usr/bin/env python2
from sqlalchemy import schema, create_engine
from sqlalchemy.orm import sessionmaker
import stratum
import subprocess
import sys
# from model import models
# from termcolor import colored

def main():
    dbEngine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost', echo=False)
    Session = sessionmaker(bind=dbEngine)
    session = Session()
    current_database = None
    list_of_main_operations = {
        1: {
            "operation": "Show",
            "sub_menu": {
                1: {
                    "operation": "Show Proxy Users",
                    "query": " \
                                SELECT ProxyUser.id, ProxyUser.userId, User.username AS userUsername, ProxyUser.username, ProxyUser.password FROM ProxyUser \
                                JOIN User ON User.id = userId\
                             ",
                    "message": "All Proxy Users"
                },
                2: {
                    "operation": "Show Users",
                    "query": "SELECT * FROM User",
                    "message": "All Users"
                },
                3: {
                    "operation": "Show Workers",
                    "query": " \
                                SELECT Worker.id, Worker.userId, User.username AS userUsername, Worker.name, Worker.password FROM Worker \
                                JOIN User ON User.id = userId\
                             ",
                    "message": "All Workers"
                },
                4: {
                    "operation": "Show Pools (Services)",
                    "query": " \
                                SELECT Service.id, serviceTypeId, ServiceType.name AS serviceTypeName, port, hostId, Host.name AS hostName, active FROM Service \
                                JOIN ServiceType ON ServiceType.id = serviceTypeId \
                                JOIN Host ON Host.id = hostId \
                             ",
                    "message": "All Pools"
                },
                5: {
                                # SELECT WorkerService.id, workerId, Worker.name as workerName, CONCAT(Host.name, ':', Service.port) as service_creds, WorkerService.active, accepted, rejected FROM WorkerService \
                    "operation": "Show WorkerService Connections",
                    "query": " \
                                SELECT WorkerService.id, workerId, Worker.name as workerName, Host.name, Service.port, WorkerService.active, accepted, rejected FROM WorkerService \
                                JOIN Worker ON Worker.id = WorkerService.workerId \
                                JOIN Service ON Service.id = WorkerService.serviceId  \
                                JOIN Host ON Host.id = Service.hostId \
                             ",
                    "message": "All WorkerService Connections"
                },
                6: {
                    "operation": "Show Coins",
                    "query": "SELECT * FROM Coin",
                    "message": "All Coins"
                },
                7: {
                    "operation": "Show Hosts",
                    "query": "SELECT * FROM Host",
                    "message": "All Hosts"
                },
                8: {
                    "operation": "Show ServiceTypes",
                    "query": "SELECT * FROM ServiceType",
                    "message": "All ServiceTypes"
                },
                9: {
                    "operation": "Show ServiceTypes",
                    "query": "SELECT * FROM ServiceType",
                    "message": "All ServiceTypes"
                },
                10: {
                    "operation": "Show UserCoin Connections",
                    "query": " \
                                SELECT UserCoin.id, userId, User.username as userUsername, coinId, Coin.name as coinName, mine, active, accepted FROM UserCoin \
                                JOIN User ON User.id = UserCoin.userId \
                                JOIN Coin ON Coin.id = UserCoin.coinId  \
                             ",
                    "message": "All Coins"
                },
            }
        },
        2: {
            "operation": "Insert",
            "sub_menu": {
                1: {
                    "operation": "Add User",
                    "query": "add_user",
                    "message": "All Users"
                },
                2: {
                    "operation": "Add Proxy User",
                    "query": "add_proxy_user",
                    "message": "All Proxy Users"
                },
                3: {
                    "operation": "Add Worker",
                    "query": "add_worker",
                    "message": "All Workers"
                },
                4: {
                    "operation": "Add Pool (Service)",
                    "query": "add_service",
                    "message": "All Pools"
                },
                5: {
                    "operation": "Add ServiceType",
                    "query": "add_service_type",
                    "message": "All Pools"
                },
                6: {
                    "operation": "Add Coin",
                    "query": "add_coin",
                    "message": "All Pools"
                },
                7: {
                    "operation": "Add Host",
                    "query": "add_host",
                    "message": "All Pools"
                },
                8: {
                    "operation": "Add UserCoin Connection",
                    "query": "add_user_coin",
                    "message": "All Pools"
                },
                9: {
                    "operation": "Add WorkerService Connection",
                    "query": "add_worker_service",
                    "message": "All Pools"
                },
            }
        },
        # 3: {
        #     "operation": "Update",
        # },
    }
    all_databases = session.execute("SHOW DATABASES").fetchall()
    databases = {}
    count = 1
    for ls in all_databases:
        for db in ls:
            if db not in ['information_schema', 'mysql', 'performance_schema']:
                databases[count] = db
                count += 1

    # print databases
    keep_program_running = True

    print "---------------------------------------"
    print "Welcome to the Interactive Console!"
    current_operation = 0
    current_sub_operation = 0

    while keep_program_running:
        while current_database is None:
            print "---------------------------------------"
            print "Select Database to work:"
            for ls in databases:
                print "%d: %s" % (ls, databases[ls])
            print "0: Quit"
            choice = raw_input()
            try:
                choice = int(choice)
                if choice in databases:
                    current_database = databases[choice]
                    dbEngine = create_engine('mysql+mysqldb://root:jfdojfoed8@localhost/' + current_database, echo=False)
                    Session = sessionmaker(bind=dbEngine)
                    session = Session()
                elif choice == 0:
                    keep_program_running = False
                    current_operation = -1
                    current_sub_operation = -1
                    break
                else:
                    print "Wrong choice!"
            except ValueError:
                print "Wrong choice!"

        while current_operation == 0:
            print "---------------------------------------"
            print "Select Operation:"
            for op in list_of_main_operations:
                print "%d: %s" % (op, list_of_main_operations[op]['operation'])
            print "0: Quit"
            choice = raw_input()
            try:
                choice = int(choice)
                # print choice
                if choice in list_of_main_operations:
                    current_operation = choice
                    current_sub_operation = 0
                elif choice == 0:
                    keep_program_running = False
                    current_operation = -1
                    current_sub_operation = -1
                    break
                else:
                    print "Wrong choice!"
            except ValueError:
                print "Wrong choice!"
                continue

        while current_sub_operation == 0:
            print "---------------------------------------"
            print "Select sub-operation:"
            for sop in list_of_main_operations[current_operation]['sub_menu']:
                print "%d: %s" % (sop, list_of_main_operations[current_operation]['sub_menu'][sop]['operation'])
            print "99: Reselect operation:"
            print "0: Quit"
            choice = raw_input()
            if current_operation == 1:
                try:
                    choice = int(choice)
                    if choice in list_of_main_operations[current_operation]['sub_menu']:
                        # current_sub_operation = choice
                        query = list_of_main_operations[current_operation]['sub_menu'][choice]['query']
                        # print list_of_main_operations[current_operation]['sub_menu'][choice]['message']
                        subprocess.call("mysql -D %s -e '%s'" % (current_database, query), shell=True)
                        # print current_sub_operation
                    elif choice == 0:
                        keep_program_running = False
                        current_sub_operation = -1
                        current_operation = -1
                    elif choice == 99:
                        current_operation = 0
                        current_sub_operation = -1
                        break
                    else:
                        print "Wrong choice!"
                    continue
                except ValueError:
                    print "Wrong choice!"
            elif current_operation == 2:
                try:
                    choice = int(choice)
                    if choice in list_of_main_operations[current_operation]['sub_menu']:
                        # current_sub_operation = choice
                        query = list_of_main_operations[current_operation]['sub_menu'][choice]['query']
                        result = insert_func(session, query)
                        # print list_of_main_operations[current_operation]['sub_menu'][choice]['message']
                        # subprocess.call("mysql -D %s -e '%s'" % (current_database, query), shell=True)
                        # print current_sub_operation
                    elif choice == 0:
                        keep_program_running = False
                        current_sub_operation = -1
                        current_operation = -1
                    elif choice == 99:
                        current_operation = 0
                        current_sub_operation = -1
                        break
                    else:
                        print "Wrong choice!"
                    continue
                except ValueError:
                    print "Wrong choice!"

            # elif current_operation == 3:
            #     print current_operation


def insert_func(session, query):
    if query == 'add_user':
        add_user(session)
    elif query == 'add_proxy_user':
        option = None
        while option is None:
            print "---------------------------------------"
            print "Select option:"
            print "1: Add ProxyUser to new User"
            print "2: Add ProxyUser to existing User"
            print "0: Quit"
            choice = raw_input()
            try:
                choice = int(choice)
                option = choice
                if choice == 1:
                    user_id = add_user(session)
                    add_proxy_user(session, user_id)
                elif choice == 2:
                    users = get_all_users(session, True)
                    user = None
                    while user == None:
                        print "---------------------------------------"
                        print "Select User:"
                        for usr in users:
                            print "%d: %s" % (usr, users[usr])
                        print "0: Quit"
                        choice = raw_input()
                        try:
                            user_id = int(choice)
                            user = add_proxy_user(session, user_id)
                            return user
                        except ValueError:
                            print "Wrong value!"
                elif choice == 0:
                    return
            except ValueError:
                print "Wrong value!"
    elif query == 'add_worker':
        option = None
        while option is None:
            print "---------------------------------------"
            print "Select option:"
            print "1: Add Worker to new User"
            print "2: Add Worker to existing User"
            print "0: Break"
            choice = raw_input()
            try:
                choice = int(choice)
                option = choice
                if choice == 1:
                    user_id = add_user(session)
                    add_worker(session, user_id)
                elif choice == 2:
                    users = get_all_users(session, True)
                    user = None
                    while user == None:
                        print "---------------------------------------"
                        print "Select User:"
                        for usr in users:
                            print "%d: %s" % (usr, users[usr])
                        print "0: Break"
                        choice = raw_input()
                        if choice == '0':
                            return
                        try:
                            user_id = int(choice)
                            user = add_worker(session, user_id)
                        except ValueError:
                            print "Wrong value!"
                elif choice == '0':
                    return
            except ValueError:
                print "Wrong value!"
        # ToDo Add functionality for associating newly worker with Service
    elif query == 'add_host':
        host_id = add_host(session)
        return host_id
    elif query == 'add_service_type':
        service_type_id = add_service_type(session)
        return service_type_id
    elif query == 'add_service':
        st_option = None
        while st_option is None:
            print "---------------------------------------"
            print "Select option:"
            print "1: Add Service to new ServiceType"
            print "2: Add Service to existing ServiceType"
            print "0: Quit"
            choice = raw_input()
            try:
                choice = int(choice)
                st_option = choice
                if choice == 1:
                    service_type_id = add_service_type(session)
                elif choice == 2:
                    service_types = get_all_service_types(session, True)
                    service_type_id = None
                    while service_type_id == None:
                        print "---------------------------------------"
                        print "Select ServiceType:"
                        for st in service_types:
                            print "%d: %s" % (st, service_types[st])
                        print "0: Break"  # ToDo
                        choice = raw_input()
                        if choice == '0':
                            return
                        try:
                            service_type_id = int(choice)
                        except ValueError:
                            print "Wrong value!"
                elif choice == '0':
                    return
            except ValueError:
                st_option = None
                print "Wrong value!"
                continue
        h_option = None
        while h_option is None:
            print "---------------------------------------"
            print "Select option:"
            print "1: Add Service to new Host"
            print "2: Add Service to existing Host"
            print "0: Break"
            choice = raw_input()
            if choice == '0':
                return
            try:
                choice = int(choice)
                h_option = choice
                if choice == 1:
                    host_id = add_host(session)
                elif choice == 2:
                    hosts = get_all_hosts(session, True)
                    host_id = None
                    while host_id == None:
                        print "---------------------------------------"
                        print "Select host:"
                        for h in hosts:
                            print "%d: %s" % (h, hosts[h])
                        print "0: Break"  # ToDo
                        choice = raw_input()
                        if choice == '0':
                            return
                        try:
                            host_id = int(choice)
                        except ValueError:
                            print "Wrong value!"
                elif choice == 0:
                    return
            except ValueError:
                h_option = None
                print "Wrong value!"
                continue
        service_id = add_service(session, service_type_id, host_id)
        return service_id
    elif query == 'add_coin':
        coin_id = add_coin(session)
        return coin_id
    elif query == 'add_user_coin':
        users = get_all_users(session, True)
        user_id = None
        while user_id == None:
            print "---------------------------------------"
            print "Select User:"
            for usr in users:
                print "%d: %s" % (usr, users[usr])
            print "0: Break"
            choice = raw_input()
            if choice == '0':
                return
            try:
                user_id = int(choice)
            except ValueError:
                print "Wrong value!"
        coins = get_all_coins(session, True)
        coin_id = None
        while coin_id == None:
            print "---------------------------------------"
            print "Select Coin:"
            for coin in coins:
                print "%d: %s" % (coin, coins[coin])
            print "0: Break"
            choice = raw_input()
            if choice == 0:
                return
            try:
                coin_id = int(choice)
            except ValueError:
                print "Wrong value!"
        user_coin_id = add_user_coin(session, user_id, coin_id)
        return user_coin_id
    elif query == 'add_worker_service':
        workers = get_all_workers(session, True)
        worker_id = None
        while worker_id == None:
            print "---------------------------------------"
            print "Select Worker:"
            for worker in workers:
                print "%d: %s" % (worker, workers[worker])
            print "0: Break"
            choice = raw_input()
            if choice == '0':
                return
            try:
                user_id = int(choice)
            except ValueError:
                print "Wrong value!"
        services = get_all_services(session, True)
        service_id = None
        while service_id == None:
            print "---------------------------------------"
            print "Select Service:"
            for service in services:
                print "%d: %s" % (service, services[service])
            print "0: Break"
            choice = raw_input()
            if choice == '0':
                return
            try:
                service_id = int(choice)
            except ValueError:
                print "Wrong value!"
        worker_service_id = add_worker_service(session, worker_id, service_id)
        return worker_service_id


def add_user(session):
    username = None
    password = None
    while username is None:
        print "---------------------------------------"
        print "Enter User Username:"
        test_username = raw_input()
        # print test_username
        result = session.execute("SELECT * FROM User WHERE username = :username", {'username': test_username}).first()
        # print result
        if result is None:
            username = test_username
        else:
            print "Wrong username! There is already a User with this username"
    while password is None:
        print "---------------------------------------"
        print "Enter User Password:"
        test_password = raw_input()
        password = test_password
    result = session.execute(
        "INSERT INTO User (username, password) VALUES (:username, :password)",
        {
            'username': username,
            'password': password,
        }
    )
    session.flush()
    session.commit()
    print "User %s:%s was added successfully" % (username, password)
    # print chr(27) + "[2J"
    return result.lastrowid


def add_proxy_user(session, user_id):
    username = None
    password = None
    while username is None:
        print "---------------------------------------"
        print "Enter ProxyUser Username:"
        test_username = raw_input()
        # print test_username
        result = session.execute("SELECT * FROM ProxyUser WHERE username = :username", {'username': test_username}).first()
        # print result
        if result is None:
            username = test_username
        else:
            print "Wrong username! There is already a ProxyUser with this username"
    while password is None:
        print "---------------------------------------"
        print "Enter ProxyUser Password:"
        test_password = raw_input()
        password = test_password
    result = session.execute(
        "INSERT INTO ProxyUser (userId, username, password) VALUES (:user_id, :username, :password)",
        {
            'user_id': int(user_id),
            'username': username,
            'password': password,
        }
    )
    session.flush()
    session.commit()
    print "ProxyUser %s:%s was added successfully to User with id %s" % (username, password, str(user_id))
    return result.lastrowid


def add_worker(session, user_id):
    name = None
    password = None
    while name is None:
        print "---------------------------------------"
        print "Enter Worker name:"
        test_name = raw_input()
        # print test_name
        result = session.execute("SELECT * FROM Worker WHERE name = :name AND userId = :user_id", {'name': test_name, 'user_id': user_id}).first()
        # print result
        if result is None:
            name = test_name
        else:
            print "Wrong name! There is already a Worker with this name"
    while password is None:
        print "---------------------------------------"
        print "Enter Worker Password:"
        test_password = raw_input()
        password = test_password
    result = session.execute(
        "INSERT INTO Worker (userId, name, password) VALUES (:user_id, :name, :password)",
        {
            'user_id': int(user_id),
            'name': name,
            'password': password,
        }
    )
    session.flush()
    session.commit()
    print "Worker %s:%s was added successfully to User with id %s" % (name, password, str(user_id))
    return result.lastrowid


def add_host(session):
    name = None
    while name is None:
        print "---------------------------------------"
        print "Enter Host name:"
        test_name = raw_input()
        result = session.execute("SELECT * FROM Host WHERE name = :name", {'name': test_name}).first()
        if result is None:
            name = test_name
        else:
            print "Wrong name! There is already a Host with this name"
    result = session.execute(
        "INSERT INTO Host (name) VALUES (:name)",
        {
            'name': name,
        }
    )
    session.flush()
    session.commit()
    print "Host %s was added successfully" % name
    return result.lastrowid


def add_service_type(session):
    name = None
    while name is None:
        print "-----------------------"
        print "Enter ServiceType name:"
        test_name = raw_input()
        result = session.execute("SELECT * FROM ServiceType WHERE name = :name", {'name': test_name}).first()
        if result is None:
            name = test_name
        else:
            print "Wrong name! There is already a ServiceType with this name"
    result = session.execute(
        "INSERT INTO ServiceType (name) VALUES (:name)",
        {
            'name': name,
        }
    )
    session.flush()
    session.commit()
    print "ServiceType %s was added successfully" % name
    return result.lastrowid


def add_service(session, service_type_id, host_id):
    port = None
    while port is None:
        print "-----------------------"
        print "Enter Service port:"
        test_port = raw_input()
        # print test_port
        try:
            port = int(test_port)
        except ValueError:
            print "Wrong port! It should be numerical!"
    result = session.execute(
        "INSERT INTO Service (serviceTypeId, port, hostId) VALUES (:serviceTypeId, :port, :hostId)",
        {
            'serviceTypeId': int(service_type_id),
            'port': int(port),
            'hostId': int(host_id),
        }
    )
    session.flush()
    session.commit()
    host = session.execute("SELECT * FROM Host WHERE id = :host_id", {'host_id': host_id}).first()
    # print(host)
    service_type = session.execute("SELECT * FROM ServiceType WHERE id = :service_type_id", {'service_type_id': service_type_id}).first()
    # print(service_type)
    print "Service(%s) %s:%s was added successfully" % (str(service_type['name']), str(host['name']), str(port))
    return result.lastrowid


def add_coin(session):
    name = None
    symbol = None
    while name is None:
        print "---------------------------------------"
        print "Enter Coin Name:"
        test_name = raw_input()
        if test_name:
            # print test_name
            result = session.execute("SELECT * FROM Coin WHERE name = :name", {'name': test_name}).first()
            # print result
            if result is None:
                name = test_name
            else:
                print "Wrong name! There is already a Coin with this name"
    while symbol is None:
        print "---------------------------------------"
        print "Enter Coin Symbol:"
        test_symbol = raw_input()
        test_symbol = str(test_symbol)
        if 0 > len(test_symbol) < 3:
            result = session.execute("SELECT * FROM Coin WHERE symbol = :symbol", {'symbol': test_symbol}).first()
            # print result
            if result is None:
                symbol = test_symbol
            else:
                print "Wrong symbol! There is already a Coin with this symbol"
        else:
            print ("Coin symbol's length should be from 0 to 3 chars!")
    result = session.execute(
        "INSERT INTO Coin (name, symbol) VALUES (:coin, :symbol)",
        {
            'name': name,
            'symbol': symbol,
        }
    )
    session.flush()
    session.commit()
    print "Coin %s(%s) was added successfully" % (name, symbol)
    # print chr(27) + "[2J"
    return result.lastrowid


def add_user_coin(session, user_id, coin_id):
    user = session.execute("SELECT * FROM User WHERE User.id = :user_id", {'user_id': user_id}).first()
    coin = session.execute("SELECT * FROM Coin WHERE Coin.id = :coin_id", {'coin_id': coin_id}).first()
    check = session.execete(
        "SELECT * FROM UserCoin WHERE userId = :user_id AND coinId = :coin_id",
        {
            'user_id': user_id,
            'coin_id': coin_id,
        }
    ).first()
    if check is not None:
        print "There is already UserCoin connection %s<->%s" % (str(user['username']), str(coin['name']))
        return None

    result = session.execute(
        "INSERT INTO UserCoin (userId, coinId) VALUES (:user_id, :coin_id)",
        {
            'user_id': user_id,
            'coin_id': coin_id,
        }
    )
    session.flush()
    session.commit()
    print "UserCoin connection %s<->%s was added successfully" % (str(user['username']), str(coin['name']))
    # print chr(27) + "[2J"
    return result.lastrowid


def add_worker_service(session, worker_id, service_id):
    worker = session.execute("SELECT * FROM Worker WHERE Worker.id = :worker_id", {'worker_id': worker_id}).first()
    service = session.execute("SELECT * FROM Service WHERE Service.id = :service_id", {'service_id': service_id}).first()
    check = session.execete(
        "SELECT * FROM WorkerService WHERE workerId = :worker_id AND serviceId = :service_id",
        {
            'worker_id': worker_id,
            'service_id': service_id,
        }
    ).first()
    if check is not None:
        print "There is already WorkerService connection %s<->%s" % (str(worker['username']), str(service['name']))
        return None

    result = session.execute(
        "INSERT INTO WorkerService (workerId, serviceId) VALUES (:worker_id, :service_id)",
        {
            'worker_id': worker_id,
            'service_id': service_id,
        }
    )
    session.flush()
    session.commit()
    print "WorkerService connection %s<->%s was added successfully" % (str(worker['username']), str(service['name']))
    # print chr(27) + "[2J"
    return result.lastrowid


def get_all_users(session, in_list=False):
    all_users = session.execute("SELECT * FROM User").fetchall()
    users = {}
    if in_list:
        for usr in all_users:
            users[usr['id']] = usr['username']
        # print users
        return users
    else:
        return all_users


def get_all_coins(session, in_list=False):
    all_coins = session.execute("SELECT * FROM Coin").fetchall()
    coins = {}
    if in_list:
        for coin in all_coins:
            coins[coin['id']] = coin['name']
        # print coins
        return coins
    else:
        return all_coins


def get_all_services(session, in_list=False):
    all_services = session.execute(
        " \
            SELECT Service.id, serviceTypeId, ServiceType.name AS serviceTypeName, port, hostId, Host.name AS hostName, active FROM Service \
            JOIN ServiceType ON ServiceType.id = serviceTypeId \
            JOIN Host ON Host.id = hostId \
        ").fetchall()
    services = {}
    if in_list:
        for service in all_services:
            services[service['id']] = str(service['hostName']) + ":" + str(services['port'])
        # print services
        return services
    else:
        return all_services


def get_all_hosts(session, in_list=False):
    all_hosts = session.execute("SELECT * FROM Host").fetchall()
    hosts = {}
    if in_list:
        for hst in all_hosts:
            hosts[hst['id']] = hst['name']
        # print hosts
        return hosts
    else:
        return all_hosts


def get_all_workers(session, in_list=False):
    all_workers = session.execute("SELECT * FROM Worker").fetchall()
    workers = {}
    if in_list:
        for worker in all_workers:
            workers[worker['id']] = worker['name']
        # print workers
        return workers
    else:
        return all_workers


def get_all_service_types(session, in_list=False):
    all_service_types = session.execute("SELECT * FROM ServiceType").fetchall()
    service_types = {}
    if in_list:
        for st in all_service_types:
            service_types[st['id']] = st['name']
        # print service_types
        return service_types
    else:
        return all_service_types

if __name__ == '__main__':
    main()