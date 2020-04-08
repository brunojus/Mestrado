import argparse
import socket
import sys
import threading
import hashlib
import os
import click

class client:
    def __init__(self, cname, cport, rname, rport):
        self.cn = cname
        self.cp = cport
        self.rn = rname
        self.rp = rport

    def listensocket(self):
        global sock
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            print('Failed to create socket. Error code: ' + str(msg))
            sys.exit()
        try:
            sock.bind((self.cn, self.cp))
        except socket.error as msg:
            print('Bind failed. Error Code : ' + str(msg))
            sys.exit()
        sock.listen(10)

        while 1:
            conn, addr = sock.accept()
            req = conn.recv(1024)
            req = req.decode('utf-8')
            reqpro = req.split('|')
            if not req:
                break
            elif (reqpro[0] == "STORE") and (reqpro[1] == "RESP"):
                # Handles response with address of node to store
                # STORE|RESP|KEY|NODENAME|NODEPORT
                nname = reqpro[3]
                nport = int(reqpro[4])
                key = reqpro[2]
                f1 = keystore[key]
                f1name = os.path.basename(f1)
                f1read = open('dht', 'r')
                f1val = f1read.read()
                data2 = "STORE|OBJ|"+key+"|"+f1name+"|"+f1val
                f1read.close()
                sendrequest(nname, nport, data2)

            elif (reqpro[0] == "ITER"):
                # Display  and store the object returned after iterative query
                # ITER|YES|NODENAME|NODEPORT|KEY|OBJECTNAME|OBJECTVALUE
                key = reqpro[4]
                print(key)
                objectname = reqpro[5]
                objectvalue = reqpro[6]
                objfile = open('dht', 'a')
                objfile.write(objectname + ':' + key+'\n')
                objfile.close
                print("Object retreived by iteratively querying the CHORD peers\n")
                


def menuopt(node):
    while 1:
        menu_opt = input(
            "1. Salvar um objeto \n2. Recuperar um objeto de um nó\n3. Sair- e\n ")

        if menu_opt == "1":
            filepath = input(
                "Insira o caminho do arquivo:\nExemplo: /home/user/filename.txt\n")
            filename = os.path.basename(filepath)
            key = hashlib.sha1(filename.encode('utf-8')).hexdigest()
            keystore[key] = filepath
            store_lookup = "STORE|OBJ|"+key+"|"+dclient.cn+"|"+str(dclient.cp)
            sendrequest(dclient.rn, dclient.rp, store_lookup)
            print("Store  request sent")
        elif menu_opt == "2":
            keyval = input(
                "Enter the key value of the object to be retreived.")
            keyval = hashlib.sha1(keyval.encode('utf-8')).hexdigest()
            iter_lookup = "RETREIVE|ITER|"+keyval + \
                "|"+dclient.cn+"|"+str(dclient.cp)
            sendrequest(dclient.rn, dclient.rp, iter_lookup)

        elif menu_opt == "3":
            print("Saindo...")
            sys.exit()
        else:
            print("Comando inválido")
            sys.exit()


def sendrequest(remotehost, remoteport, senddata):
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    remote_ip = socket.gethostbyname(remotehost)
    sock2.connect((remote_ip, remoteport))
    sock2.sendall(senddata.encode('utf-8'))
    sock2.close()


@click.group(invoke_without_command=True)
@click.option('-p', '--client_port', type=int,
              help='Specify the port for the peer')
@click.option('-h', '--client_hostname',
              help='Specify the hostname of the peer')
@click.option('-r', '--root_port', type=int,
              help='Specify the port of the root')
@click.option('-R', '--root_hostname',
              help='Specify the hostname of the root')
def start(client_port, client_hostname, root_port, root_hostname):
    global keystore
    keystore = {}

    dclient = client(client_hostname, client_port, root_hostname, rootport)

    sockcl = threading.Thread(target=dclient.listensocket)
    menu = threading.Thread(target=menuopt, args=(dclient,))
    sockcl.start()
    menu.start()
