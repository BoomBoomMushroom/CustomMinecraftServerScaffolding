import threading

import world
import server

worldThread = threading.Thread(target=world.World.run, args=(), daemon=True)
worldThread.start()

serverThread = threading.Thread(target=server.startSocketServer, args=(), daemon=True)
serverThread.start()

# A while loop to keep the world and server threads running
try:
    while True: pass
except KeyboardInterrupt as e:
    server.s.close() # close socekt and end (gracefully?)
    exit()
except Exception as e: raise e


