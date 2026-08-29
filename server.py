import packets
import client

import socket
import threading

def handleClient(conn: socket.socket, addr: socket._RetAddress):
    print(f"Connected by {addr}")
    clientObj = client.Client()

    while True:
        try:
            # Read in data
            disconnectClient = False
            while True:
                try:
                    read = conn.recv(1024)
                    clientObj.readInBytes(read)

                    # NOTHING to read, returned None, meaning we gotta close the connection
                    if not read:
                        disconnectClient = True
                        break
                except BlockingIOError: # No data to read
                    break
            if disconnectClient == True: break

            if clientObj.queuedOutboundPackets == None: break

            # Send queue outbound packets
            packetsSent = 0
            while len(clientObj.queuedOutboundPackets) > 0:
                if packetsSent >= 10: break # handle newer packets first then send out new ones, this way we don't lock up just sending stuff
                outbound: packets.Packet = clientObj.queuedOutboundPackets.pop(0) # pop 1st for FIFO behaviour
                rawBytes = outbound.getSendingBytes()
                # print that we're sending a packet only if it's the first time we're sending it, not if we're continuing a partial packet
                if outbound.rawBytesOffset == 0: print("Sending packet:", outbound)
                try:
                    dataSent = conn.send(rawBytes)
                    outbound.reportAmountOfBytesSent(dataSent)
                    if outbound.isPacketFullySent() == False:
                        # we haven't fully sent the packet, insert it back in so we can continue sending it's data
                        clientObj.queuedOutboundPackets.insert(0, outbound)
                    else: packetsSent += 1 # yay we sent it! increment our counter
                except BlockingIOError as e:
                    clientObj.queuedOutboundPackets.insert(0, outbound)
                    break
                except Exception as e: raise e

        except ConnectionResetError:
            print(f"Client {addr} has disconnected")
            break

    conn.close()
    print(f"Connection with {addr} closed")

s: socket.socket = None

def startSocketServer():
    global s
    HOST = "localhost"
    PORT = 25565

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Enable reuse to prevent "Address already in use" when debugging
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server started on {HOST}:{PORT}")

    while True:
        # accept a connection
        conn, addr = s.accept()
        conn.setblocking(False) # make the sockets not blocking

        t = threading.Thread(target=handleClient, args=(conn,addr), daemon=True)
        t.start()


if __name__ == "__main__":
    startSocketServer()

