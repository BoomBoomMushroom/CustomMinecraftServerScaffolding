import packets
import client

import socket
import threading

HOST = "localhost"
PORT = 25565


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

            # Send queue outbound packets
            while len(clientObj.queuedOutboundPackets) > 0:
                outbound: packets.Packet = clientObj.queuedOutboundPackets.pop(0) # pop 1st for FIFO behaviour
                print("Sending packet:", outbound)
                packetBytes = outbound.getRawBytes()
                try:
                    conn.send(packetBytes)
                except BlockingIOError as e:
                    clientObj.queuedOutboundPackets.insert(0, outbound)
                    break
                except Exception as e: raise e

        except ConnectionResetError:
            print(f"Client {addr} has disconnected")
            break

    conn.close()
    print(f"Connection with {addr} closed")


if __name__ != "__main__": exit()
# everything after here executes if we are on main

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

