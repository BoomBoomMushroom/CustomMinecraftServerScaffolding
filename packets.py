import dataTypes
from ServerSettings import ServerSettings

from typing import Literal
import time
import json
import requests

BoundDirection = Literal["ServerBound", "ClientBound"]
ConnectionState = Literal["HANDSHAKING", "STATUS", "LOGIN", "CONFIGURATION", "PLAY"]

# https://minecraft.wiki/w/Java_Edition_protocol/Packets#List_of_packets

class Packet:
    def __init__(self, id: int, name: str, data: bytearray=bytearray(0), boundDir: BoundDirection="ServerBound", connState: ConnectionState="HANDSHAKING"):
        self.id: int = id # ex 0x01
        self.name: str = name # ex. status_request
        self.data: bytearray = data # body of the packet, it's data

        self.boundDirection: BoundDirection = boundDir # ServerBound or ClientBound
        self.connectionState: ConnectionState = connState # Handshaking, status, login, configuration, or play

    def getRawBytes(self) -> bytes:
        packetIdVarIntBytes: bytes = dataTypes.writeVarInt(self.id)
        packetLength = len(packetIdVarIntBytes) + len(self.data)
        lengthVarIntBytes: bytes = dataTypes.writeVarInt( packetLength )

        return lengthVarIntBytes + packetIdVarIntBytes + self.data

    def handle(self) -> HandleResponse:
        print(self.data)
        raise NotImplementedError(f"`handle` not implemented on main Packet class, make an override for: {self.__str__()}")

    def __str__(self):
        idHex = "0x" + (hex(self.id).split("0x")[1]).zfill(2)

        return f"[{self.connectionState}] Direction: {self.boundDirection}, ID: {idHex}, Name: {self.name}"

# Handshaking packets
class Intention_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "intention", data, "ServerBound", "HANDSHAKING")
    def handle(self):
        toConsumeData = self.data
        protocolVersion, bytesRead = dataTypes.readVarInt(toConsumeData)
        toConsumeData = toConsumeData[bytesRead:]
        serverAddress, bytesRead = dataTypes.readString(toConsumeData)
        toConsumeData = toConsumeData[bytesRead:]
        serverPort, bytesRead = dataTypes.readUnsignedShort(toConsumeData)
        toConsumeData = toConsumeData[bytesRead:]
        intent, bytesRead = dataTypes.readVarInt(toConsumeData)
        toConsumeData = toConsumeData[bytesRead:]
        #print(protocolVersion, serverAddress, serverPort, intent)

        response = HandleResponse()
        if intent == 1: response.nextConnectionState = "STATUS"
        if intent == 2 or intent == 3: response.nextConnectionState = "LOGIN"

        return response

# Status packets
class StatusResponse_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "status_response", data, "ClientBound", "STATUS")
class StatusResponse_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "status_response", data, "ServerBound", "STATUS")
    def handle(self):
        responseJson = {
            "version": {
                "name": ServerSettings.version,
                "protocol": ServerSettings.protocol
            },
            "player": {
                "max": ServerSettings.maxPlayers,
                "online": ServerSettings.playersOnline,
                "sample": []
            },
            "description": {
                "text": ServerSettings.motd
            },
            "favicon": ServerSettings.serverIcon,
            "enforcesSecureChat": False
        }
        jsonBytes = dataTypes.writeString(json.dumps(responseJson))
        responseOut = HandleResponse()
        responseOut.respondWithPackets.append( StatusResponse_ClientBound(jsonBytes) )

        return responseOut

class PongResponse_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1, "pong_response", data, "ClientBound", "STATUS")
class PingResponse_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1, "ping_response", data, "ServerBound", "STATUS")
    def handle(self):
        responseLong = round(time.time() * 1000)
        responseBytes: bytes = bytes()
        responseBytes += dataTypes.writeSignedLong(responseLong)

        response = HandleResponse()
        response.respondWithPackets.append(PongResponse_ClientBound( responseBytes ))
        return response

# Login packets
class Hello_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "hello", data, "ServerBound", "LOGIN")
    def handle(self):
        consumeData = self.data
        name, bytesRead = dataTypes.readString(consumeData)
        consumeData = consumeData[bytesRead:]
        UUID, bytesRead = (consumeData[:16], 16)
        consumeData = consumeData[bytesRead:]

        #print(name, uuidString)
        response = HandleResponse()
        response.updateUsername = name
        response.updateUUID = UUID

        # If we don't want to do encryption or compression go right on into finishing the login procedure
        loginFinishedPacket = LoginFinished_ClientBound()
        loginFinishedPacket.createFromUUID(UUID)
        response.respondWithPackets.append(loginFinishedPacket)

        return response

class LoginAcknowledged_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3, "login_acknowledged", data, "ServerBound", "LOGIN")
    def handle(self):
        response = HandleResponse()
        response.nextConnectionState = "CONFIGURATION"

        # send register packets since we're gonna skip "plugin message", "feature flags", and "known packs"
        response.generateAndSendRegistryData = True

        return response
class LoginFinished_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2, "login_finished", data, "ClientBound", "LOGIN")

    def createFromUUID(self, UUID: bytes):
        self.data = bytes() # clear the data to override it
        
        uuidString = "".join([ hex(b).split("0x")[1].zfill(2) for b in UUID ])
        r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuidString}?unsigned=false")
        mcData = r.json()

        # Write Game Profile
        self.data += UUID
        self.data += dataTypes.writeString(mcData["name"])
        self.data += dataTypes.writeVarInt(1)
        self.data += dataTypes.writeString(mcData["properties"][0]["name"])
        self.data += dataTypes.writeString(mcData["properties"][0]["value"])
        self.data += dataTypes.writeBoolean(True) # if we dont want the signiture then set it to false and comment out the next line
        self.data += dataTypes.writeString(mcData["properties"][0]["signature"])
        # Write Session ID (as a UUID)
        self.data += bytes(16) # I don't think it matters what I make the UUID, so it'll be all 0s for rn

# Configuration packets
class ClientInformation_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "client_information", data, "ServerBound", "CONFIGURATION")
    def handle(self):
        toConsume = self.data
        locale, bytesRead = dataTypes.readString(toConsume)
        toConsume = toConsume[bytesRead:]
        viewDist, bytesRead = (toConsume[0], 1)
        toConsume = toConsume[bytesRead:]
        chatMode, bytesRead = dataTypes.readVarInt(toConsume)
        toConsume = toConsume[bytesRead:]
        chatColors, bytesRead = (toConsume[0], 1)
        toConsume = toConsume[bytesRead:]
        displayedSkinParts, bytesRead = (toConsume[0], 1)
        toConsume = toConsume[bytesRead:]
        mainHand, bytesRead = dataTypes.readVarInt(toConsume)
        toConsume = toConsume[bytesRead:]
        enableTextFiltering, bytesRead = (toConsume[0], 1)
        toConsume = toConsume[bytesRead:]
        allowServerListings, bytesRead = (toConsume[0], 1)
        toConsume = toConsume[bytesRead:]
        particleStatus, bytesRead = dataTypes.readVarInt(toConsume)
        toConsume = toConsume[bytesRead:]
        print(locale, viewDist, chatMode, chatColors, displayedSkinParts, mainHand, enableTextFiltering, allowServerListings, particleStatus)

class RegistryData_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x7, "registry_data", data, "ClientBound", "CONFIGURATION")
    def __str__(self):
        return super().__str__() + ", Register: " + dataTypes.readIdentifier(self.data)[0]

class FinishConfiguration_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3, "finish_configuration", data, "ClientBound", "CONFIGURATION")
class FinishConfiguration_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3, "finish_configuration", data, "ServerBound", "CONFIGURATION")
    def handle(self):
        response = HandleResponse()
        response.nextConnectionState = "PLAY"

        response.giveLoginPacket = True

        return response

class UpdateTags_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xD, "update_tags", data, "ClientBound", "CONFIGURATION")

# Play packets
class Login_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x31, "login", data, "ClientBound", "PLAY")

class ClientTickEnd_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0d, "client_tick_end", data, "ServerBound", "PLAY")
    def handle(self):
        return

# Extra classes
class HandleResponse:
    def __init__(self):
        # connection updates
        self.respondWithPackets: list[Packet] = []
        self.nextConnectionState: ConnectionState = None

        # update client specific values
        self.updateUsername: str = None
        self.updateUUID: str = None

        # client todo flags:
        self.generateAndSendRegistryData = False
        self.giveLoginPacket = False
        self.stuffAfterLoginPacket = False



# Decoding and other packet stuff

HANDSHAKING_PACKETS = [Intention_ServerBound]
STATUS_PACKETS = [
    StatusResponse_ClientBound, StatusResponse_ServerBound,
    PongResponse_ClientBound, PingResponse_ServerBound
]
LOGIN_PACKETS = [
    Hello_ServerBound,
    LoginFinished_ClientBound, LoginAcknowledged_ServerBound
]
CONFIGURATION_PACKETS = [
    ClientInformation_ServerBound,
    RegistryData_ClientBound,
    FinishConfiguration_ClientBound, FinishConfiguration_ServerBound,
    UpdateTags_ClientBound
]
PLAY_PACKETS = [
    Login_ClientBound,

    ClientTickEnd_ServerBound,
]

def decodePacket(data: bytes, connState: ConnectionState) -> tuple[bytes, Packet]:
    if len(data) <= 0: return (data, None) # No bytes... We can't do anything that that!
    offset = 0
    packetLength, bytesRead = dataTypes.readVarInt(data[offset:]) # len of packetId + dataBytes
    if (len(data) - offset) < packetLength: return (data, None) # We haven't read enough bytes!

    offset += bytesRead
    packetId, bytesRead = dataTypes.readVarInt(data[offset:])
    offset += bytesRead

    endIndex = offset+packetLength-1 # minus 1 to not read one extra byte since packetId is included in that length
    dataBytes = data[offset : endIndex]
    offset += packetLength-1

    # packetLength, packetId, dataBytes
    returnRemainingBytes = data[endIndex:] # everything after the data
    packet: Packet = None

    #print(packetLength, packetId, dataBytes, data)
    packetClasses = []

    if connState == "HANDSHAKING": packetClasses = HANDSHAKING_PACKETS
    elif connState == "STATUS": packetClasses = STATUS_PACKETS
    elif connState == "LOGIN": packetClasses = LOGIN_PACKETS
    elif connState == "CONFIGURATION": packetClasses = CONFIGURATION_PACKETS
    elif connState == "PLAY": packetClasses = PLAY_PACKETS

    for packetType in packetClasses:
        packet = packetType(dataBytes)
        if (packet.boundDirection != "ServerBound") or (packet.id != packetId):
            # Either we're not serverbound or the packet IDs don't match up! Either way it's the wrong packet
            packet = None # make sure we clear the packet else it could lead to a false positive
            continue
        break # all good, break to continue

    if packet == None:
        packetId = "0x" + (hex(packetId).split("0x")[1]).zfill(2)
        print(f"Unknown packet state and or id! {packetId=} {connState=}")

    return (returnRemainingBytes, packet)

