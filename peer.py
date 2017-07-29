#!/usr/bin/python3.4

import socket, sys, _thread, os, getopt, threading, random

global port
global looping
global queuedReq
global reqID

looping = True
reqID = 0
queuedReq = []


#-l specifies the peer's listening address <address>:<port>
#-p specifies a neighboring peer of the form <address>:<port>
def getUserArgs():
    #initialize the needed vars
    listenPort = 0
    neighborList = []

    #parse user args
    try:    
        optlist, args = getopt.gnu_getopt(sys.argv, 'l:p:')
    except getopt.GetoptError as msg:
        print('Invalid command line options\n' + str(msg))
        sys.exit()

    #loop through all options from the optlist. 
    #if one exists attach the peer's listener to the specified listening address.
    #if any exist add each peer to the neighborList.
    for option in optlist:
        if option[0] == '-l':
            listenPort = int(option[1])
        elif option[0] == '-p':
            neighborList.append(option[1])

    return (listenPort, neighborList)
    
#Bind our listening socket.
def bindToListener(listenSocket, listenPort):
    global port
    if listenPort == 0:
        #Bind socket to local host and port
        try:
            #Bind the socket to the localhost on a randomly available port
            listenSocket.bind(('', 0))
            #Update the global listener port for this listener thread.
            port = str(listenSocket.getsockname()[1])
            listenPort = port
            print('Socket bind complete')  
            print('Socket now listening on port: ' + str(listenPort))        
        except socket.error as msg:
            print('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
            sys.exit()        
    else:
        #Bind socket to local host and port
        try:
            #Bind the socket to the localhost on the user provided port
            listenSocket.bind(('', listenPort))
            port = str(listenSocket.getsockname()[1])
            print('Socket bind complete')  
            print('Socket now listening on port: ' + str(listenPort))
        except socket.error:
            print('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
            sys.exit()    
    return listenPort    

#Validate our potential peers.    
def validatePeer(peer):
    #Split the peer into <address> and <port> delimited by :
    peerSplit = peer.split(':')
    
    #Validate that our port we have a two part address and that the port is an integer value
    if len(peerSplit) == 2:
        try:
            int(peerSplit[1])
            return True
        except ValueError:
            print(peerSplit[1] + ' is an invalid port.')
            return False
    else:
        print(peerSplit[0] + ' is an invalid address.')
        return False

#Create the topology.        
def createTopology(neighborList, listenPort):    
    newneighborList = []
    for peer in neighborList:
            #Verify the peer is in our current neighborList
            if peer not in newneighborList:
                #Validate that the peer is of the correct format
                if validatePeer(peer):
                    try:
                        #Create a connection to inform the peer it's been added as a neighbor, and add it to the neighbor list.
                        peerSplit = peer.split(':')
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.connect((peerSplit[0], int(peerSplit[1])))
                        s.send(('connect ' + socket.getfqdn() + ':' + str(listenPort)).encode('ascii'))
                        data = s.recv(1024).decode()
                        newneighborList.append(peer) 
                        print(data)          

                    except socket.error:    
                        print('Unable to connect to ' + peer)
            else:
                print('This peer is connected to ' + peer)

    return newneighborList

#Leave the topology.    
def exitTopology(neighborList, listenPort):
    #Iterate the peer's in the neighborList
    for peer in neighborList:
        try:
            #Create a socket and inform each peer they have been removed as a neighbor, so they may remove the exiting node.
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
            peerSplit = peer.split(':')
            s.connect((peerSplit[0], int(peerSplit[1])))
            s.send(('disconnect ' + socket.getfqdn() + ':' + str(listenPort)).encode('ascii'))
            data = s.recv(1024).decode()
            if data:
                if len(neighborList) > 0:
                    s.send(random.choice(neighborList[0]).encode('ascii'))
                else:
                    s.send(''.encode('ascii'))
            else:
                s.send(''.encode('ascii'))
            s.close()
            print('Disconnected from ' + peer)                
        except socket.error:    
            print('Unable to connect to ' + peer)
        
#Serve each request the listener received.
def serveRequest(conn, address, listenPort, neighborList):
    #Process request messages
    request = conn.recv(1024).decode()
    request = request.split()
    if request[0] == 'connect':
        neighborList.append(request[1])
        data = request[1] + ' was added to the neighborList on ' + socket.getfqdn() + ':' + str(listenPort)
        conn.send(data.encode('ascii'))
        
    elif request[0] == 'disconnect':
        if(request[1] in neighborList):
            neighborList.remove(request[1])
        data = request[1] + ' was removed from the neighborList on ' + socket.getfqdn() + ':' + str(listenPort)
        conn.send(data.encode('ascii'))
                
    elif request[0] == 'search':
        data = lookupFile(request[2], neighborList, request[1],listenPort)
        if len(data) > 1:
            conn.send(data[0].encode('ascii'))
        
    elif request[0] == 'fetch':
        #extract the fileName
        fileName = request[1]
            #inform the user that a dowload request has come in 
        print(address[0] + ':' + str(address[1]) + ' has requested to fetch file: ' + fileName)
        print('\nEnter command:')
            #open the requested file for reading
        fileReq = open(fileName, 'rb')

        #read in and send the file to the requestor
        data = fileReq.read(1024)
        while data:
                conn.send(data)
                data = fileReq.read(1024)
            #send an empty string to let the requestor know the file is complete
        conn.send(''.encode('ascii'))
        #close the connection
    conn.close()
    
#Listen for connection reqeusts.
#Create a new thread to process requests.
def activateListener(listener, neighborList, listenPort):
    #Start listening on socket
    listener.listen(10)
    while looping:
        #Accept connections.
        (conn, address) = listener.accept()

        #Create a seperate thread to handle any file requests.
        if looping:
            reqThread = threading.Thread(target=serveRequest, args=(conn, address, listenPort, neighborList))
            reqThread.start()    

#Identify local files.            
def searchFilesLocal():
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    return files

#Locate a file within the network.    
def lookupFile(filename, neighborList, requestID, listenPort):
    #Maintain a global list of requested downloads incase multiple clients have requested
    #simultaenously 
    global queuedReq
    #String that will contain peers from network that have the requested file.
    filePeer = []
    #Check if our current requestId is already in our pendingLookups
    if requestID not in queuedReq:
        #Add the current requestId to our queuedReq list.
        queuedReq.append(requestID)
        #Split the request ID back into it's fully qualified domain name, port, and reqID
        reqIDSplit = requestID.split(':')
        #Check if the current peer is the original peer who submitted the request.
        if reqIDSplit[0] != socket.getfqdn() or int(reqIDSplit[1]) != listenPort:
            #Grab the list of local files for this peer.
            fileList = searchFilesLocal()
            #If the file we are looking for is in the local files list,
            if filename in fileList:
                #Add this peer to the string which will contain our address hits in the file search
                filePeer.append(socket.getfqdn() + ':' + str(listenPort))
        #Now check the neighbor's of this peer to see if the file exists on any of them.
        for neighbor in neighborList:
            #Create a new socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #Split the address into it's components.
            nbrSplit = neighbor.split(':')
            try:
                s.connect((nbrSplit[0],int(nbrSplit[1])))
                s.send(('search ' + requestID + ' ' + filename).encode('ascii'))
                filePeer.append(s.recv(1024).decode())
                s.close
            except:
                print('Connection failed.')
                pass
                
        queuedReq.remove(requestID)
    return filePeer                         
            
#Download a file from the network.
def fetch(neighborList, cmd, listenPort):
    #This global is used to created unique queues for handling simultaenous file requests.
    global reqID
    #Make sure a fileName was provided
    fileName = cmd[1]    
    if len(cmd) == 2:
        files = searchFilesLocal()        
        #Check if the file exists locally.
        if cmd[1] in files:
            print(fileName + ' is a local file.\n')
        #Check for the file in the network            
        else:
            #Create a unique identifier for this peer's specific file request.
            requestID = socket.getfqdn() + ':' + str(listenPort) + ':' + str(reqID)
            #Increment global ID value to allow concurrent file requests.
            reqID += 1
            #List of peers who have this file available.
            filePeers = lookupFile(fileName, neighborList, requestID, listenPort)            
            if any(':' in peer for peer in filePeers):
                #Grab the file from one of the returned peers.
                [address, port] = random.choice(filePeers).split(':')
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((address,int(port)))
                s.send(('fetch '+ fileName).encode('ascii'))
                #open a file for writing
                fileRec = open(fileName, 'wb')
                #read in data and write it to the file until complete
                data = s.recv(1024)
                while data:
                    fileRec.write(data)
                    data = s.recv(1024)
                fileRec.close()
                s.close()
                print(fileName + ' successfully downloaded.')
            else:
                print('File could not be located in this network.')
    else:
        print('usage: fetch <filename>\n')

#Allow access to the topology.        
def connect(listenPort, cmd, neighborList, client):
    #Make sure our command is of the right length.
    if len(cmd) > 1:
        #Remove the first element of the command ('connect')
        cmd.pop(0)
        #Iterate through the peers remaining in the command.
        for peer in cmd:
            #Verify the peer is in our current neighborList
            if peer not in neighborList:
                #Validate that the peer is of the correct format
                if validatePeer(peer):
                    try:
                        #Create a connection to inform the peer it's been added as a neighbor, and add it to the neighbor list.
                        peerSplit = peer.split(':')
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.connect((peerSplit[0], int(peerSplit[1])))
                        s.send(('connect ' + socket.getfqdn() + ':' + str(listenPort)).encode('ascii'))
                        data = s.recv(1024).decode()
                        neighborList.append(peer)                        
                        if client:
                            print(data)          
                        s.close()
                    except socket.error:    
                        print('Unable to connect to ' + peer)
            else:
                print('This peer is connected to ' + peer)
    else:
        print('usage connect <peer1> <peer2> ...<peerN>\n') 

#Remove a node from the topology.        
def disconnect(listenPort, cmd, neighborList, client):
    #Make sure our command is of the right length.
    if len(cmd) > 1:
        #Remove the first element of the command ('disconnect')
        cmd.pop(0)
        #Iterate through the peers remaining in the command.
        for peer in cmd:
            #Verify the peer is in our current neighborList
            if peer in neighborList:
                try:
                    #Remove the peer, then open a connection to notify the peer it was removed.
                    neighborList.remove(peer)
                    peerSplit = peer.split(':')
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((peerSplit[0], int(peerSplit[1])))
                    s.send(('disconnect ' + socket.getfqdn() + ':' + str(listenPort)).encode('ascii'))
                    data = s.recv(1024).decode()
                    if data:
                        if len(neighborList) > 0:
                            s.send(random.choice(neighborList[0]).encode('ascii'))
                        else:
                            s.send(''.encode('ascii'))
                    s.close()
                    print('Disconnected from ' + peer)                
                except socket.error:    
                    print('Unable to connect to ' + peer)                        
            else:
                print('This peer is not connected.')
    else:
        print('usage disconnect <peer1> <peer2> ...<peerN>\n')         

#Provides basic user I/O and command interfacing via a loop.        
def peerInterface(neighborList, listenPort):
    print('\nAdvanced OS Project 2\nPeer Interface\nEnter \'help\' for a list of commands')
    
    while True:
        cmd = input('Enter Command\n').split()
        cmd[0] = cmd[0].lower()
        if len(cmd) == 0:
            print('No command entered\n')
        elif cmd[0] == 'neighbors':
            print(str(neighborList) + '\n')            
        elif cmd[0] == 'fetch':
            if len(cmd) == 2:
                fetch(neighborList, cmd, listenPort)
            else:
                print('usage: fetch <filename>\n')
        elif cmd[0] == 'connect':
            if len(cmd) >= 2:
                connect(listenPort, cmd, neighborList, True)
            else:
                print('usage connect <peer1> <peer2> ...<peerN>\n') 
        elif cmd[0] == 'disconnect':
            if len(cmd) >= 2:
                disconnect(listenPort, cmd, neighborList, True)                
            else:
                print('usage disconnect <peer1> <peer2> ...<peerN>\n') 
        elif cmd[0] == 'help':
            print('Command List: fetch, neighbors, connect, disconnect, exit.\n')
        elif cmd[0] == 'exit':
            break
        else:
            print(cmd[0] + ' is not a recognized command, please enter a recognized command or \'help\' for a command list.\n')

#Cleanly exit the program, closing all connections and removing the node from the topology.            
def cleanExit(listenSocket, listenPort, neighborList):
    #Allows us to stop looping through user input from the peerInterface
    global looping 
    looping = False
    
    #Socket created to close out of listner.
    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    c.connect((socket.getfqdn(), int(listenPort)))
    c.close()   
    
    exitTopology(neighborList, listenPort)   
    listenSocket.close()

#Main Loop
def main():
    #Create a new socket.
    listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    #Get the specified listening address, and neighboring peer list if the 
    #user provided one via the command line.
    (listenPort, neighborList) = getUserArgs()
    
    #Create a thread based listener for incoming connections.
    listenPort = bindToListener(listenSocket, listenPort)

    #Create the network topology between the various peers.
    neighborList = createTopology(neighborList, listenPort)


    #Start the listener thread.
    listeningThread = threading.Thread(target=activateListener, args=(listenSocket, neighborList, listenPort))
    listeningThread.start()

    #Request user input (this is a loop).
    peerInterface(neighborList, listenPort)

    #Gracefully exit the program
    cleanExit(listenSocket, listenPort, neighborList)
    
main()    