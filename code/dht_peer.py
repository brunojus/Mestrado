import argparse
import socket
import sys
import hashlib
import click

class node:
    # Class that defines the current node
    def __init__(self, phname, phport, nname, nport, shname, shport, identity):
        self.pn = phname
        self.pp = phport
        self.nn = nname
        self.np = nport
        self.sn = shname
        self.sp = shport
        self.id = identity

    def listensocket(self):
        # Function for creating a socket on the node to listen.
        global sock1
        try:
            sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            print('Failed to create socket. Error code: ' + str(msg))
            sys.exit()
        try:
            sock1.bind((self.nn, self.np))
        except socket.error as msg:
            print('Bind failed. Error Code : ' + str(msg))
            sys.exit()
        sock1.listen(10)
        return sock1

    def printchord(self):
        # Function to printcurrent node positon
        print("Updated node position\n_____________")
        print("Node ID:", self.id)
        print("Predecessor:", self.pn, ":", self.pp)
        print("This node:", self.nn, ":", self.np)
        print("Successor:", self.sn, ":", self.sp, "\n")


def sendrequest(clientHostname, clientPort, senddata):
    # Function to send requests and responses to specified targets
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    remote_ip = socket.gethostbyname(clientHostname)
    sock2.connect((remote_ip, int(clientPort)))
    sock2.sendall(senddata.encode('utf-8'))
    sock2.close()


def rootjoin(indata, nodeval):
    # Function that handles JOIN requests to the root
    # 1. Update the predecessor of the current successor
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    remote_ip = socket.gethostbyname(nodeval.sn)
    sock2.connect((remote_ip, int(nodeval.sp)))
    predupdata = "UPDATE|PRED|" + indata[1]+"|"+indata[2]
    sock2.sendall(predupdata.encode('utf-8'))
    sock2.close()
    # 3. Update the successor of the root node
    nodeval.sn = indata[1]
    nodeval.sp = indata[2]


def predup(indata, nodeval, conn):
    # Handling predecessor update requests
    nodeval.pn = indata[2]
    nodeval.pp = indata[3]
    conn.close()


def succup(indata, nodeval, conn):
    # Handling successor update requests
    nodeval.sn = indata[2]
    nodeval.sp = indata[3]
    conn.close()


def nodejoin(rh, rp, oh, op):
    # Sending JOIN request to root node
    sock3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rootip = socket.gethostbyname(rh)
    sock3.connect((rootip, rp))
    joindata = 'JOIN|' + str(oh) + '|' + str(op)

    sock3.sendall(joindata.encode())
    data = sock3.recv(1024)
    data = data.decode('utf-8')
    print(data)
    datadelim = data.split('|')
    return datadelim


def leavechord(node):
    # UPDATE|PRED|HOSTNAME|PORT
    data1 = "UPDATE|PRED|"+node.pn+"|"+str(node.pp)
    sendrequest(node.sn, node.sp, data1)
    # UPDATE|SUCC|HOSTNAME|PORT
    data2 = "UPDATE|PRED|"+node.sn+"|"+str(node.sp)
    sendrequest(node.pn, node.pp, data2)
    sys.exit()

# Parsing the arguments as needed
@click.group(invoke_without_command=True)
@click.option('-m', '--peertype', type=int,
              help='Specify 1 if the peer is root and 0 otherwise')
@click.option('-p', '--own_port', type=int,
              help='Specify the port for the peer')
@click.option('-h', '--own_hostname',
              help='Specify the hostname of the peer')
@click.option('-r', '--root_port', type=int,
              help='Specify the port of the root')
@click.option('-R', '--root_hostname',
              help='Specify the hostname of the root')
def start(peertype, own_port, own_hostname, root_port, root_hostname):
    # Default is normal peer if the type is not specified.
    if peertype is None:
        peertype = 0

    iden = 0
    cnt = 0
    keystore = {}  # The dictionary which holds key values and filenames

    # If m = 1, the node initiated is considered as the root node.
    if peertype == 1:
        # Initiating root node
        rootnode = node(own_hostname, own_port, own_hostname, own_port, own_hostname, own_port, iden)
        rootnode.printchord()
        # Creating a socket for root node
        sock_root = rootnode.listensocket()
        while 1:
            print("count now is %d" % (cnt+1))
            conn, addr = sock_root.accept()
            req = conn.recv(1024)
            req = req.decode('utf-8')
            reqpro = req.split('|')
            if not req:
                break
            elif reqpro[0] == "COUNT":
                print("Node count updated on the entire CHORD")
                sendrequest(rootnode.pn, rootnode.pp, req)
            elif reqpro[0] == "JOIN":
                # If the request is from a new node to join the CHORD
                # JOIN|HOSTNAME|PORT
                # Respond to the new node with information of its would be successor
                sucupdate = "UPDATE|SUCC|"+rootnode.sn + \
                    "|"+str(rootnode.sp)+"|"+str(cnt)
                conn.sendall(sucupdate.encode('utf-8'))
                conn.close()
                # Invoke the root join routine
                rootjoin(reqpro, rootnode)
                rootnode.printchord()
                cnt += 1  # Increment number of nodes
                print("Number of nodes in the CHORD now is %d" % (cnt+1))
                print("Updating node count info to other nodes")
                #mes = "COUNT|"+str(cnt+1)
                # sendrequest(rootnode.pn,rootnode.pp,mes)
            elif (reqpro[0] == 'UPDATE') and (reqpro[1] == 'PRED'):
                # If the request is to update the predecessor of rootnode, invoke predup routine
                # UPDATE|PRED|HOSTNAME|PORT
                predup(reqpro, rootnode, conn)
                rootnode.printchord()
            elif (reqpro[0] == 'STORE') and (reqpro[1] == 'POS'):
                # If the request is from a client to find the node to store an object
                # STORE|POS|KEY|CLIENTNAME|CLIENTPORT
                print("Store Message")
                key = reqpro[2]
                k = "0x"+reqpro[2]
                keynum = int(k, 0) % (cnt+1)
                cln = reqpro[3]
                clp = int(reqpro[4])
                if keynum == rootnode.id:
                    # If the ID of the node corresponds to object ID, send store response to client.
                    resptocl = "STORE|RESP|"+key+"|" + \
                        rootnode.nn+"|"+str(rootnode.np)
                    resptocl = resptocl.encode('utf-8')
                    sendrequest(cln, clp, resptocl)
                else:
                    forwardstore = req+"|"+str(cnt+1)
                    # If ID doesn't correspond to, forward the message to predecessor
                    sendrequest(rootnode.pn, rootnode.pp, forwardstore)
            elif (reqpro[0] == 'STORE') and (reqpro[1] == 'OBJ'):
                # If the request from client is to store the object
                # STORE|OBJ|KEY|OBJNAME|OBJVALUE
                key = reqpro[2]
                objectname = reqpro[3]
                keystore[key] = objectname
                objectvalue = reqpro[4]
                objfile = open('dht', 'a')
                objfile.write(objectname + ':' + key+'\n')
                print("Object %s stored on this node\n %s" %
                    (objectname, objectvalue))
            elif (reqpro[0] == 'RETREIVE') and (reqpro[1] == 'ITER'):
                # If the request is to look for an object in iterative manner.
                # RETREIVE|ITER|KEY|CLIENTNAME|CLIENTPORT
                key = reqpro[2]
                if keystore[key]:
                    objname = keystore[key]
                    print("The requested object %s is available on the node. Object name is %s" % (
                        key, objname))
                    objval = open('dht', 'r')
                    resp = "ITER|YES|"+rootnode.nn+"|" + \
                        str(rootnode.np)+"|"+key+"|"+objname+"|"+str(objval)
                    objval.close()
                    sendrequest(reqpro[3], int(reqpro[4]), resp)
                    print("Object %s sent to the client" % objname)
                else:
                    # If the key is not present return the predecessor identity
                    print("The object %s is not present on this node." % key)
                    resp = "ITER|NO|"+key+"|"+rootnode.pn+"|"+str(rootnode.pp)
                    sendrequest(reqpro[3], int(reqpro[4]), resp)

            else:
                print("invalid request type")
                sys.exit()
    elif peertype == 0:
        # Initiate a normal node with predecessor as root and successor as empty and node ID as 0
        normalnode = node(root_hostname, root_port, own_hostname, own_port, '', 0, 0)
        # Sending JOIN request to root node
        joinhandle = nodejoin(root_hostname, root_port, own_hostname, own_port)
        # joinhandle returns "UPDATE|SUCC|NODEID|NODEPORT|COUNT
        normalnode.sn = joinhandle[2]
        normalnode.sp = int(joinhandle[3])
        normalnode.id = int(joinhandle[4])+1
        normalnode.printchord()
        # Creating a socket for normal node
        sock_normal = normalnode.listensocket()
        while 1:
            conn, addr = sock_normal.accept()
            # Handling the incoming requests received
            nreq = conn.recv(1024)
            nreq = nreq.decode('utf-8')
            nreqpro = nreq.split('|')
            if not nreq:
                break
            elif nreqpro[0] == 'COUNT':
                cnt += 1
                print(nreqpro[1])
                print("Number of nodes ", cnt)
                sendrequest(normalnode.pn, normalnode.pp, nreq)
            elif (nreqpro[0] == 'UPDATE') and (nreqpro[1] == 'SUCC'):
                # If the request is update successor request
                # UPDATE|SUCC|HOSTNAME|PORT
                succup(nreqpro, normalnode, conn)
                normalnode.printchord()
            elif (nreqpro[0] == 'UPDATE') and (nreqpro[1] == 'PRED'):
                # If the request is update predecessor request
                # UPDATE|PRED|HOSTNAME|PORT
                predup(nreqpro, normalnode, conn)
                normalnode.printchord()
            elif (nreqpro[0] == 'STORE') and (nreqpro[1] == 'POS'):
                # If the request is from a client to find the node to store an object
                # STORE|POS|KEY|CLIENTNAME|CLIENTPORT|COUNT

                key = nreqpro[2]
                k = "0x"+nreqpro[2]
                keynum = int(k, 0) % int(nreqpro[5])
                cln = nreqpro[3]
                clp = int(nreqpro[4])
                if keynum == normalnode.id:
                    # If the ID of the node corresponds to object ID, send store response to client.
                    resptocl = "STORE|RESP|"+key+"|" + \
                        normalnode.nn+"|"+str(normalnode.np)
                    sendrequest(cln, clp, resptocl)
                else:
                    # If ID doesn't correspond to, forward the message to predecessor
                    sendrequest(normalnode.pn, normalnode.pp, nreq)
            elif (nreqpro[0] == 'STORE') and (nreqpro[1] == 'OBJ'):
                # If the request from client is to store the object
                # STORE|OBJ|KEY|OBJNAME|OBJVALUE
                key = nreqpro[2]
                objectname = nreqpro[3]
                keystore[key] = objectname
                objectvalue = nreqpro[4]
                objfile = open('dht', 'a')
                objfile.write(objectname + ':' + key+'\n')
                print("Object %s stored on this node\n %s" %
                    (objectname, objectvalue))

            elif (nreqpro[0] == 'RETREIVE') and (nreqpro[1] == 'ITER'):
                # If the request is to look for an object in iterative manner.
                # RETREIVE|ITER|KEY|CLIENTNAME|CLIENTPORT
                key = nreqpro[2]
                if keystore[key]:
                    # If the key is present on node, return the object
                    objname = keystore[key]
                    objval = open('dht', 'r')
                    resp = "ITER|YES|"+normalnode.nn+"|" + \
                        str(normalnode.np)+"|"+key+"|"+objname+"|"+objval
                    objval.close()
                    sendrequest(nreqpro[3], int(nreqpro[4]), resp)
                    print("Object %s sent to the client" % objname)
                else:
                    # If the key is not present return the predecessor identity
                    print("The object %s is not present on this node." % key)
                    resp = "ITER|NO|"+key+"|"+normalnode.pn+"|"+str(normalnode.pp)
                    sendrequest(nreqpro[3], int(nreqpro[4]), resp)
            elif (nreqpro[0] == 'RETREIVE') and (nreqpro[1] == 'REC'):
                # If the request is to look for an object in resursive manner.
                # RETREIVE|RECU|KEY|CLIENTNAME|CLIENTPORT
                key = nreqpro[2]
                if keystore[key]:
                    # If the key is present on the node, return the object
                    objname = keystore[key]
                    print("The requested object %s is available on the node. Object name is %s" % (
                        key, objname))
                    objval = open('dht', 'r')
                    resp = "RECU|"+key+normalnode.nn+"|" + \
                        str(normalnode.np)+"|"+objname+"|"+objval
                    objval.close()
                    sendrequest(nreqpro[3], int(nreqpro[4]), resp)
                else:
                    # If the key is not present, forward the request to the predecessor
                    print("The requested object %s is not present on the node" % key)
                    sendrequest(normalnode.pn, normalnode.pp, nreq)
            else:
                print("invalid request type")
                sys.exit()
    else:
        print("Invalid peertype")
        sys.exit()
