import packets
import dataTypes

class Client:
    def __init__(self):
        self.username = ""
        self.UUID = ""

        self.state: packets.ConnectionState = "HANDSHAKING"
        self.data: bytes = bytes()
        self.unhandledPackets: list[packets.Packet] = []
        self.queuedOutboundPackets: list[packets.Packet] = []

    def readAllPackets(self):
        while True:
            # typing is given by the return typing of decodePacket (a tuple[bytes, Packet])
            self.data, packet = packets.decodePacket(self.data, self.state)
            if packet == None: break
            self.unhandledPackets.append(packet)

    def handlePacketReturn(self, packetResponse: packets.HandleResponse):
        if packetResponse == None: return

        # connection updates
        self.queuedOutboundPackets.extend( packetResponse.respondWithPackets )
        if packetResponse.nextConnectionState != None: self.state = packetResponse.nextConnectionState

        # update the client's data
        if packetResponse.updateUsername != None: self.username = packetResponse.updateUsername
        if packetResponse.updateUUID != None: self.UUID = packetResponse.updateUUID

        # client todo stuff
        if packetResponse.generateAndSendRegistryData == True: self.generateAndSendRegistryData()
        

    def handlePackets(self):
        self.readAllPackets()

        while len(self.unhandledPackets) > 0:
            packet = self.unhandledPackets.pop(0) # pop the first one for a FIFO queue
            print(packet)
            response = packet.handle()
            self.handlePacketReturn(response)

    def readInBytes(self, newData: bytes):
        self.data += newData
        self.handlePackets()

    def generateAndSendRegistryData(self):
        
        pass

