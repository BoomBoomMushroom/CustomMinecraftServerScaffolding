from dataTypes import PacketDataWriter, PacketDataReader
from ServerSettings import ServerSettings
from enumValues import *
from Registry import Registry

import time
import json


# https://minecraft.wiki/w/Java_Edition_protocol/Packets#List_of_packets

class Packet:
    def __init__(self, id: int, name: str, data: bytearray=bytearray(0), boundDir: BoundDirection="ServerBound", connState: ConnectionState="HANDSHAKING"):
        if type(data) == PacketDataWriter:
            # we forgot to use `.data` on it, do it here
            data = data.data
        
        self.id: int = id # ex 0x01
        self.name: str = name # ex. status_request
        self.data: bytearray = data # body of the packet, it's data

        self.boundDirection: BoundDirection = boundDir # ServerBound or ClientBound
        self.connectionState: ConnectionState = connState # Handshaking, status, login, configuration, or play

        self.fullPacketData = None
        self.rawBytesOffset: int = 0

    def getRawBytes(self) -> bytes:
        if self.fullPacketData != None: return self.fullPacketData
        packetIdWriter = PacketDataWriter()
        packetIdWriter.writeVarInt(self.id)
        
        packetLength = len(packetIdWriter) + len(self.data)
        lengthVarWriter = PacketDataWriter()
        lengthVarWriter.writeVarInt( packetLength )

        self.fullPacketData: bytes = lengthVarWriter.data + packetIdWriter.data + self.data

        return self.fullPacketData

    def getSendingBytes(self) -> bytes:
        return self.getRawBytes()[self.rawBytesOffset:]
    def reportAmountOfBytesSent(self, num: int): self.rawBytesOffset += num
    def isPacketFullySent(self) -> bool: return self.rawBytesOffset >= len(self.getRawBytes())
    
    def addToBytesOffset(self, toAdd: int):
        self.rawBytesOffset += toAdd

    def handle(self) -> HandleResponse:
        print(self.data)
        raise NotImplementedError(f"`handle` not implemented on main Packet class, make an override for: {self.__str__()}")

    @classmethod
    def write(self) -> Packet:
        raise NotImplementedError(f"`write` not implemented on main Packet class, make an override for: {self.__str__()}")

    def __str__(self):
        idHex = "0x" + (hex(self.id).split("0x")[1]).zfill(2)

        return f"[{self.connectionState}] Direction: {self.boundDirection}, ID: {idHex}, Name: {self.name}"

# Handshaking packets
class Intention_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "intention", data, "ServerBound", "HANDSHAKING")
    def handle(self):
        reader = PacketDataReader(self.data)
        protocolVersion = reader.readVarInt()
        serverAddress = reader.readString()
        serverPort = reader.readUnsignedShort()
        intent = reader.readVarInt()
        #print(protocolVersion, serverAddress, serverPort, intent)

        response = HandleResponse()
        if intent == 1: response.nextConnectionState = "STATUS"
        if intent == 2 or intent == 3: response.nextConnectionState = "LOGIN"

        return response

# Status packets
class StatusResponse_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "status_response", data, "ClientBound", "STATUS")
    
    @classmethod
    def write(cls, versionName, protocolId, maxPlayers, playerOnline, samplePlayerPool, motd, favicon, usesSecureChat):
        responseJson = {
            "version": {
                "name": versionName,
                "protocol": protocolId
            },
            "player": {
                "max": maxPlayers,
                "online": playerOnline,
                "sample": samplePlayerPool
            },
            "description": {
                "text": motd
            },
            "favicon": favicon,
            "enforcesSecureChat": usesSecureChat
        }
        data = PacketDataWriter()
        data.writeString(json.dumps(responseJson))
        return StatusResponse_ClientBound(data)
        
class StatusRequest_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "status_request", data, "ServerBound", "STATUS")
    def handle(self):
        srPacket = StatusResponse_ClientBound.write(
            ServerSettings.version, ServerSettings.protocol,
            ServerSettings.maxPlayers, ServerSettings.playersOnline, [],
            ServerSettings.motd, ServerSettings.serverIcon, False
        )
        
        responseOut = HandleResponse()
        responseOut.respondWithPackets.append( srPacket )

        return responseOut

class PongResponse_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1, "pong_response", data, "ClientBound", "STATUS")
class PingRequest_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1, "ping_request", data, "ServerBound", "STATUS")
    def handle(self):
        responseLong = round(time.time() * 1000)
        responseBytes = PacketDataWriter()
        responseBytes.writeLong(responseLong)

        response = HandleResponse()
        response.respondWithPackets.append(PongResponse_ClientBound( responseBytes ))
        return response

# Login packets
class Hello_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "hello", data, "ServerBound", "LOGIN")
    def handle(self):
        reader = PacketDataReader(self.data)
        name = reader.readString()
        UUID = reader.readUUID()

        #print(name, uuidString)
        response = HandleResponse()
        response.updateUsername = name
        response.updateUUID = UUID
        response.sendLoginFinishedPacket = True

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

# Configuration packets
class ClientInformation_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0, "client_information", data, "ServerBound", "CONFIGURATION")
    def handle(self):
        reader = PacketDataReader(self.data)
        locale = reader.readString()
        viewDist = reader.readByte()
        chatMode = reader.readVarInt()
        chatColors = reader.readByte()
        displayedSkinParts = reader.readByte()
        mainHand = reader.readVarInt()
        enableTextFiltering = reader.readByte()
        allowServerListings = reader.readByte()
        particleStatus = reader.readVarInt()
        print(locale, viewDist, chatMode, chatColors, displayedSkinParts, mainHand, enableTextFiltering, allowServerListings, particleStatus)

class RegistryData_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x7, "registry_data", data, "ClientBound", "CONFIGURATION")
    def __str__(self):
        reader = PacketDataReader(self.data)
        return super().__str__() + ", Register: " + reader.readIdentifier()

class FinishConfiguration_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3, "finish_configuration", data, "ClientBound", "CONFIGURATION")
class FinishConfiguration_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3, "finish_configuration", data, "ServerBound", "CONFIGURATION")
    def handle(self):
        response = HandleResponse()
        response.nextConnectionState = "PLAY"

        response.clientLoginToWorld = True

        return response

class UpdateTags_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xD, "update_tags", data, "ClientBound", "CONFIGURATION")

class CustomPayload_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2, "custom_payload", data, "ServerBound", "CONFIGURATION")
    def handle(self):
        reader = PacketDataReader(self.data)
        channel = reader.readIdentifier()

        # ehh idk how to really handle this and it really doesn't matter so im gonna ignore this
        return None
class CustomPayload_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1, "custom_payload", data, "ServerBound", "CONFIGURATION")

class UpdateEnabledFeatures_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xC, "update_enabled_features", data, "ClientBound", "CONFIGURATION")
class SelectKnownPacks_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xE, "select_known_packs", data, "ClientBound", "CONFIGURATION")

# Play packets
class Login_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x31, "login", data, "ClientBound", "PLAY")
    
    @classmethod
    def write(cls,
        eid, isHardcore, dimensions, maxPlayers, renderDist, simDist, reducedDebugInfo,
        enableRespawnScreen, doLimitedCrafting, playerDimensionIdentifier, seedHash,
        gameMode: GAMEMODE, prevGameMode: GAMEMODE, isDebugWorld, isSuperflat, hasDeathLoc, lastDeathDim, lastDeathPos,
        portalCooldown, seaLevel, isOnlineMode, enforcesSecureChat
    ):
        playData = PacketDataWriter()
        playData.writeInt(eid) # player entity id, EID
        playData.writeBoolean(isHardcore) # is hardcore
        playData.writeVarInt(len(dimensions))
        for dim in dimensions:
            playData.writeIdentifier(dim)
        playData.writeVarInt(maxPlayers) # max players, used to draw tablist but now ignored
        playData.writeVarInt(renderDist) # render distance (2-32)
        playData.writeVarInt(simDist) # simulation dist
        playData.writeBoolean(reducedDebugInfo) # reduced debug info (false for development)
        playData.writeBoolean(enableRespawnScreen) # enable respawn screen
        playData.writeBoolean(doLimitedCrafting) # do limited crafting (unused by client)
        playData.writeVarInt(
            Registry.getSyncedRegistry("minecraft:dimension_type").getEntryIndex(playerDimensionIdentifier)
        ) # dimension type id from the registry
        playData.writeIdentifier(playerDimensionIdentifier) # dimension name
        playData.writeLong(seedHash) # hashed seed, first 8 bytes of it
        playData.writeUnsignedByte(GAMEMODE_Enum[gameMode]) # game mode
        playData.writeByte(GAMEMODE_Enum[prevGameMode]) # previous gamemode, used for F3+F4. Same as above just -1 is null
        playData.writeBoolean(isDebugWorld) # is debug world
        playData.writeBoolean(isSuperflat) # is superflat world
        playData.writeBoolean(hasDeathLoc) # has death location. makes the next 2 fields present
        if hasDeathLoc:
            playData.writeIdentifier(lastDeathDim) # last death dimension name
            playData.writePosition(*lastDeathPos) # last death pos, use `*` to expand it out into x, y, and z
        playData.writeVarInt(portalCooldown) # portal cooldown in ticks
        playData.writeVarInt(seaLevel) # sea level
        playData.writeBoolean(isOnlineMode) # online mode
        playData.writeBoolean(enforcesSecureChat) # enforces secure chat
        
        return Login_ClientBound(playData)

class ClientTickEnd_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x0d, "client_tick_end", data, "ServerBound", "PLAY")
    def handle(self):
        return
class PlayerLoaded_ServerBound(Packet):
    def __init__(self, data = bytearray(0),):
        super().__init__(0x2C, "player_loaded", data, "ServerBound", "PLAY")
    def handle(self):
        pass # nothing much to really handle

class ConfigurationAcknowledge_ServerBound(Packet):
    def __init__(self, data = bytearray(0),):
        super().__init__(0x16, "configuration_acknowledge", data, "ServerBound", "PLAY")
    def handle(self):
        response = HandleResponse()
        response.nextConnectionState = "CONFIGURATION"
        response.clientLoginToWorld = False # log out of the world
        
        return response


"""Position"""
class PlayerPosition_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x48, "player_position", data, "ClientBound", "PLAY")
    
    @classmethod
    def write(cls, teleportId, posX, posY, posZ, velX, velY, velZ, yaw, pitch, teleportFlags):
        playerPosPacketData: bytes = PacketDataWriter()
        playerPosPacketData.writeVarInt(teleportId) # teleport id, will be used to confirm in confirm teleport packet
        playerPosPacketData.writeDouble(posX) # X
        playerPosPacketData.writeDouble(posY) # Y
        playerPosPacketData.writeDouble(posZ) # Z
        playerPosPacketData.writeDouble(velX) # Vx
        playerPosPacketData.writeDouble(velY) # Vy
        playerPosPacketData.writeDouble(velZ) # Vz
        playerPosPacketData.writeFloat(yaw) # yaw, in degrees
        playerPosPacketData.writeFloat(pitch) # pitch, in degrees
        playerPosPacketData.writeInt(teleportFlags) # teleport flags (https://minecraft.wiki/w/Java_Edition_protocol/Packets#Teleport_Flags)
        
        return PlayerPosition_ClientBound(playerPosPacketData)

class AcceptTeleportation_ServerBound(Packet):
    def __init__(self, data = bytearray(0),):
        super().__init__(0x0, "accept_teleportation", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        teleportId = reader.readVarInt()
        res = HandleResponse()
        res.teleportId = teleportId

        return res
class MovePlayerPos_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1E, "move_player_pos", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        x = reader.readDouble()
        feetY = reader.readDouble()
        z = reader.readDouble()
        flags = reader.readByte()

        onGround = (flags & 0x01) == 0x01
        pushingWall = (flags & 0x02) == 0x02

        res = HandleResponse()
        res.updatePosition = (x, feetY, z)
        res.updateOnGround = onGround
        res.updateAgainstWall = pushingWall
        return res
class MovePlayerPosRot_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1F, "move_player_pos_rot", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        x = reader.readDouble()
        feetY = reader.readDouble()
        z = reader.readDouble()
        yaw = reader.readFloat()
        pitch = reader.readFloat()
        flags = reader.readByte()

        onGround = (flags & 0x01) == 0x01
        pushingWall = (flags & 0x02) == 0x02

        res = HandleResponse()
        res.updatePosition = (x, feetY, z)
        res.updateRotation = (yaw, pitch)
        res.updateOnGround = onGround
        res.updateAgainstWall = pushingWall
        return res
class MovePlayerRot_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x20, "move_player_rot", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        yaw = reader.readFloat()
        pitch = reader.readFloat()
        flags = reader.readByte()

        onGround = (flags & 0x01) == 0x01
        pushingWall = (flags & 0x02) == 0x02

        res = HandleResponse()
        res.updateRotation = (yaw, pitch)
        res.updateOnGround = onGround
        res.updateAgainstWall = pushingWall
        return res
class MovePlayerStatusOnly_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x21, "move_player_status_only", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        flags = reader.readByte()

        onGround = (flags & 0x01) == 0x01
        pushingWall = (flags & 0x02) == 0x02

        res = HandleResponse()
        res.updateOnGround = onGround
        res.updateAgainstWall = pushingWall
        return res

"""Activities"""
class Swing_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3F, "swing", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        hand = reader.readVarInt()
        isMainHand = (hand==0) # if false, used offhand
        
        shr = ServerHandleResponse()
        shr.type = "swing"
        shr.swingHand = isMainHand
        return shr

class Attack_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1, "attack", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        recvEntityId = reader.readVarInt()
        
        shr = ServerHandleResponse()
        shr.type = "attack"
        shr.swingEntityId = recvEntityId
        return shr


class PlayerInput_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2b, "player_input", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        flags = reader.readUnsignedByte()
        # these flags are used for minecart controls
        forward = flags & 0x01 == 0x01
        backward = flags & 0x02 == 0x02
        left = flags & 0x04 == 0x04
        right = flags & 0x08 == 0x08
        jump = flags & 0x10 == 0x10
        sneak = flags & 0x20 == 0x20
        sprint = flags & 0x40 == 0x40
        # TODO: make it for minecart controls

class PlayerCommand_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2a, "player_command", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        eid = reader.readVarInt()
        actionId = reader.readVarInt()
        jumpBoost = reader.readVarInt() # used for horse jump only (0-100 inclusive), else it is 0

        response = HandleResponse()
        if actionId == 0:
            # leave bed
            # only sent when clicking "leave bed" in the gui, not when it becomes morning
            pass
        if actionId == 1:
            # start sprinting
            response.updateSprinting = True
        if actionId == 2:
            # stop sprinting
            response.updateSprinting = False
        if actionId == 3:
            # start jump w/ horse
            pass
        if actionId == 4:
            # stop jump w/ horse
            pass
        if actionId == 5:
            # open vehicle inventory
            # only when went pressing open inventory button while on a horse or chest boat
            pass
        if actionId == 6:
            # start flying w/ elytra
            response.updateElytraGliding = True

        return response

class PlayerAbilities_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x28, "player_abilities", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        flags = reader.readByte()
        isFlying = flags & 0x02 == 0x02
        response = HandleResponse()
        response.updateFlying = isFlying
        return response

class PlayerAction_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x29, "player_action", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        status = reader.readVarInt()
        location = reader.readPosition()
        face = reader.readByte()
        sequence = reader.readVarInt() # used to ack a block has been broken w/ that id

        # face enum -> 0=-Y, 1=+Y, 2=-Z, 3=+Z, 4=-X, 5=+X

        if status == 0:
            # start digging
            pass
        if status == 1:
            # cancelled digging
            pass
        if status == 2:
            # finished digging
            pass
        if status == 3:
            # drop item stack
            pass
        if status == 4:
            # drop item
            pass
        if status == 5:
            # shoot arrow/finish eating
            pass
        if status == 6:
            # swap item in hand
            pass
        if status == 7:
            # stab
            pass

        # TODO: have client.py valiate this by making sure the distance between our eyes and the block is <= 6
        # TODO: Have the server actually handle ts

        response = HandleResponse()
        return response

class ClientCommand_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xc, "client_command", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        actionId = reader.readVarInt()
        
        shr = ServerHandleResponse()
        shr.type = "ClientCommand"
        shr.actionId = ACTION_ID_EnumFrom[actionId]
        return shr

class ContainerButtonClick_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x11, "container_button_click", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        windowId = reader.readVarInt()
        buttonId = reader.readVarInt()
        
        shr = ServerHandleResponse()
        shr.type = "ContainerButtonClick"
        shr.windowId = windowId
        shr.buttonId = buttonId
        
        return shr

class ContainerClick_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x12, "container_click", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        windowId = reader.readVarInt()
        stateId = reader.readVarInt()
        slot = reader.readShort()
        button = reader.readByte()
        mode = reader.readVarInt()
        # 2 more things after this, array of changed slots, and carried item
        #   both use hashed slot which i haven't implemented this
        # todo: when this is implemented read them
        
        shr = ServerHandleResponse()
        shr.type = "ContainerClick"
        shr.windowId = windowId
        shr.stateId = stateId
        shr.slot = slot
        shr.button = button
        shr.mode = mode
        shr.arrOfChangedSlots = {}
        shr.carriedItem = None
        
        return shr

class ContainerSlotStateChanged_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x12, "container_slot_state_changed", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        slotId = reader.readShort()
        windowId = reader.readVarInt()
        state = reader.readBoolean()
        
        shr = ServerHandleResponse()
        shr.type = "ContainerSlotStateChanged"
        shr.slotId = slotId
        shr.windowId = windowId
        shr.slotState = state
        return shr


class ChatAck_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x6, "chat_ack", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        messageCount = reader.readVarInt(self.data)
        # i dont think we really need to do anything here.
        # TODO: fact check this ^^

class Chat_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x9, "chat", data, "ServerBound", "PLAY")
    def handle(self):
        # https://minecraft.wiki/w/Java_Edition_protocol/Packets#Chat_Message
        reader = PacketDataReader(self.data)
        message = reader.readString()
        timestamp = reader.readLong()
        salt = reader.readLong()
        isSigPresent = reader.readBoolean()
        sigBytes: list[int] = []
        if isSigPresent:
            length = reader.readVarInt() # should be 256
            for i in range(0,length):
                sigBytes.append( reader.readByte() )
        msgCount = reader.readVarInt()
        # acknowledged is a 20 bit bitset aka 2.5 bytes, so 3 bytes need to be read
        acknowledged1of3 = reader.readByte()
        acknowledged2of3 = reader.readByte()
        acknowledged3of3 = reader.readByte()
        checksum = reader.readByte()
        
        # message, timestamp, salt, sigBytes, msgCount, acknowledged1of3..., checksum
        shr = ServerHandleResponse()
        shr.type = "chat"
        shr.message = message
        shr.timestamp = timestamp
        shr.messageSalt = salt
        return shr
class PlayerChat_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x41, "player_chat", data, "ServerBound", "PLAY")
    
    @classmethod
    def write(cls, senderName: str, message: str, timestamp: int, salt: int, clientsRecvCt: int, clientsSendCt: int, senderUUID: bytes) -> PlayerChat_ClientBound:
        # https://minecraft.wiki/w/Java_Edition_protocol/Packets#Player_Chat_Message
        data = PacketDataWriter()
        
        # header
        data.writeVarInt(clientsRecvCt) # global index, for something idr
        data.writeRawBytes(senderUUID)
        data.writeVarInt(clientsSendCt) # index, somehow different than global index but im not 100% sure how
        data.writeBoolean(False) # false, i dont wanna send message signature bytes
        
        #body
        data.writeString(message)
        data.writeLong(timestamp)
        data.writeLong(salt)
        
        # idk some array
        data.writeVarInt(0)
        
        # other
        data.writeBoolean(False) # no "unsigned content" ig
        data.writeVarInt(0) # filter type | 0=message not filtered, 1=message fully filtered, 2=message partially filtered
        # data.? # only write this if the filter type is partially filtered (2)
        
        # chat formatting
        data.writeVarInt( Registry.getSyncedRegistry("minecraft:chat_type").getEntryIndex("minecraft:chat")+1 ) # +1 because this is a type "ID or X"
        data.writeTextComponentOnlyString(senderName)
        data.writeBoolean(False) # im not sending a target name
        
        return PlayerChat_ClientBound(data)

"""Updates"""
class BlockUpdate_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x8, "block_update", data, "ClientBound", "PLAY")

"""Server setting stuff"""
class ChangeDifficulty_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xA, "change_difficulty", data, "ClientBound", "PLAY")

    @classmethod
    def write(cls, difficulty: DIFFICULTY, difficultyLocked):
        changeDiffData = PacketDataWriter()
        changeDiffData.writeUnsignedByte( DIFFICULTY_Enum[difficulty] )
        changeDiffData.writeBoolean(difficultyLocked)
        return ChangeDifficulty_ClientBound(changeDiffData)

class ChangeDifficulty_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0xA, "change_difficulty", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        difficulty = reader.readUnsignedByte()
        difficultyLocked = reader.readBoolean()
        
        shr = ServerHandleResponse()
        shr.type = "changeDifficulty"
        shr.difficulty = DIFFICULTY_EnumFrom[difficulty]
        shr.difficultyLocked = difficultyLocked
        return shr

class ChangeGamemode_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x5, "change_game_mode", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        gamemode = reader.readVarInt()
        
        shr = ServerHandleResponse()
        shr.type = "changeGamemode"
        shr.gamemode: GAMEMODE = GAMEMODE_EnumFrom[gamemode] # type: ignore
        return shr


class PlayerAbilities_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x40, "player_abilities", data, "ClientBound", "PLAY")

    @classmethod
    def write(cls, isInvulnerable, isFlying, isAllowedToFly, canInstaBreakBlocks, flyingSpeed, fovModifier):
        abilitiesFlagsVal = 0
        if isInvulnerable: abilitiesFlagsVal |= 0x1
        if isFlying: abilitiesFlagsVal |= 0x2
        if isAllowedToFly: abilitiesFlagsVal |= 0x4
        if canInstaBreakBlocks: abilitiesFlagsVal |= 0x8

        playerAbilitiesData = PacketDataWriter()
        playerAbilitiesData.writeByte(abilitiesFlagsVal)
        playerAbilitiesData.writeFloat(flyingSpeed) # flying speed (default = 0.05)
        playerAbilitiesData.writeFloat(fovModifier) # fov modifier (default is 0.1?) check https://minecraft.wiki/w/Java_Edition_protocol/Packets#Player_Abilities_(clientbound)
        return PlayerAbilities_ClientBound(playerAbilitiesData)

class SetHeldSlot_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x69, "set_held_slot", data, "ClientBound", "PLAY")
    
    @classmethod
    def write(cls, slot):
        heldSlotData = PacketDataWriter()
        heldSlotData.writeVarInt(slot) # slow which the player has selected (0-8)
        return SetHeldSlot_ClientBound(heldSlotData)

class PlayerInfoUpdate_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x46, "player_info_update", data, "ClientBound", "PLAY")
    
    @classmethod
    def write(cls, piuInfoActions: list[PLAYER_INFO_UPDATE_ACTIONS], players: list):
        piuActionsFlag = 0x00
        for action in piuInfoActions:
            bitToSet = 0x00
            if action == "AddPlayer": bitToSet = 0x01
            if action == "InitializeChat": bitToSet = 0x02
            if action == "UpdateGameMode": bitToSet = 0x04
            if action == "UpdateListed": bitToSet = 0x08
            if action == "UpdateLatency": bitToSet = 0x10
            if action == "UpdateDisplayName": bitToSet = 0x20
            if action == "UpdateListPriority": bitToSet = 0x40
            if action == "UpdateHat": bitToSet = 0x80
            piuActionsFlag |= bitToSet

        piuData = PacketDataWriter()
        piuData.writeUnsignedByte(piuActionsFlag)
        piuData.writeVarInt( len(players) )
        for player in players:
            piuData.writeRawBytes(player.UUID)
            # MUST be in this order im like 99.9% certain of it
            if piuActionsFlag & 0x01 == 0x01:
                # Add player
                piuData.writeRawBytes(player.getGameProfile(ignoreUUID=True))
            if piuActionsFlag & 0x02 == 0x02:
                # Init chat
                pass # gonna skip this one since im not doing chat encryption right now
            if piuActionsFlag & 0x04 == 0x04:
                # Game Mode
                piuData.writeVarInt( GAMEMODE_Enum[player.gamemode] )
            if piuActionsFlag & 0x08 == 0x08:
                # Listed in tab list
                piuData.writeBoolean(True)
            if piuActionsFlag & 0x10 == 0x10:
                # Ping in ms
                piuData.writeVarInt(0)
            if piuActionsFlag & 0x20 == 0x20:
                # Display name
                pass # todo: when i make full text components we can send this
            if piuActionsFlag & 0x40 == 0x40:
                # List priority
                piuData.writeVarInt(0)
            if piuActionsFlag & 0x80 == 0x80:
                # is hat visible
                piuData.writeBoolean(player.isHatVisible)
        
        return PlayerInfoUpdate_ClientBound(piuData)

class InitializeBorder_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2b, "initialize_border", data, "ClientBound", "PLAY")

    @classmethod
    def write(cls, centerX, centerZ, oldDiameter, newDiameter, speed, portalTeleportBoundary, warningBlocks, warningTime):
        initWBData = PacketDataWriter()
        initWBData.writeDouble(centerX) # center x
        initWBData.writeDouble(centerZ) # center z
        initWBData.writeDouble(oldDiameter) # old diameter
        initWBData.writeDouble(newDiameter) # new diameter
        initWBData.writeVarLong(speed) # speed
        initWBData.writeVarInt(portalTeleportBoundary) # portal teleport boundary, usually 29999984
        initWBData.writeVarInt(warningBlocks) # warning blocks, in meters
        initWBData.writeVarInt(warningTime) # warning time, in seconds
        
        return InitializeBorder_ClientBound(initWBData)


class SetTime_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x71, "set_time", data, "ClientBound", "PLAY")

    @classmethod
    def write(cls, worldAge, worldClockRegEntriesAndTime):
        setTimeData = PacketDataWriter()
        setTimeData.writeLong(worldAge) # world age
        setTimeData.writeVarInt(len(worldClockRegEntriesAndTime)) # len of array of Clocks
        for clockRegId, timeOfClock, fracPart, rate in worldClockRegEntriesAndTime:
            setTimeData.writeVarInt(clockRegId) # clock registry id
            setTimeData.writeVarLong(timeOfClock) # current time of the clock
            setTimeData.writeFloat(fracPart) # fractional part of the time in ticks (non-negative num less than 1)
            setTimeData.writeFloat(rate) # rate, in clock tick per client tick
        
        # sending the time at 24000+ seems to auto modulos so we don't have to do it
        
        return SetTime_ClientBound(setTimeData)

class GameEvent_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x26, "game_event", data, "ClientBound", "PLAY")

    @classmethod
    def write(self, eventId:GAME_EVENT_ID, value: float=0):
        # https://minecraft.wiki/w/Java_Edition_protocol/Packets#Game_Event
        gameEventData = PacketDataWriter()
        gameEventData.writeUnsignedByte(eventId) # event id
        gameEventData.writeFloat(value) # value for specific events
        
        return GameEvent_ClientBound(gameEventData)

class TickingState_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x7F, "ticking_state", data, "ClientBound", "PLAY")
    
    @classmethod
    def write(self, tickRate, isTickFrozen):
        tickingStateData = PacketDataWriter()
        tickingStateData.writeFloat(tickRate) # tick rate
        tickingStateData.writeBoolean(isTickFrozen) # is frozen?
        return TickingState_ClientBound(tickingStateData)

class SetChunkCacheCenter_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x5E, "set_chunk_cache_center", data, "ClientBound", "PLAY")
        
    @classmethod
    def write(self, plrX, plrZ):
        playerChunkX = int(plrX // 16)
        playerChunkZ = int(plrZ // 16)

        setChunkCenterData = PacketDataWriter()
        setChunkCenterData.writeVarInt(playerChunkX) # chunk x
        setChunkCenterData.writeVarInt(playerChunkZ) # chunk z
        
        return SetChunkCacheCenter_ClientBound(setChunkCenterData)

class LevelChunkWithLight_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2D, "level_chunk_with_light", data, "ClientBound", "PLAY")

class SetDefaultSpawnPosition_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x61, "set_default_spawn_position", data, "ClientBound", "PLAY")

    @classmethod
    def write(cls, dimensionIdentifier, x, y, z, yaw, pitch):
        defaultSpawnData = PacketDataWriter()
        defaultSpawnData.writeIdentifier(dimensionIdentifier) # dimension
        defaultSpawnData.writePosition(x, y, z) # pos
        defaultSpawnData.writeFloat(yaw) # yaw
        defaultSpawnData.writeFloat(pitch) # pitch
        
        return SetDefaultSpawnPosition_ClientBound(defaultSpawnData)

"""Entities"""
class EntityEvent_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x22, "entity_event", data, "ClientBound", "PLAY")
    
    @classmethod
    def write(cls, eid, status):
        entityEventData = PacketDataWriter()
        entityEventData.writeInt(eid) # Entity ID
        entityEventData.writeByte(status) # 24->28 = op level 0->4 respectively
        
        return EntityEvent_ClientBound(entityEventData)

"""Misc"""
class Ping_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x3D, "ping", data, "ClientBound", "PLAY")
class Pong_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2D, "pong", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader()
        pingId = reader.readInt()
        return # nothing else to do

class KeepAlive_ClientBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x2C, "keep_alive", data, "ClientBound", "PLAY")
class KeepAlive_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x1C, "keep_alive", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        keepAliveId = reader.readLong()
        return # nothing else to do

class CookieResponse_ServerBound(Packet):
    def __init__(self, data = bytearray(0)):
        super().__init__(0x15, "cookie_response", data, "ServerBound", "PLAY")
    def handle(self):
        reader = PacketDataReader(self.data)
        key = reader.readIdentifier()
        hasData = reader.readBoolean()
        cookieData: list[int] = [] # list of bytes
        if hasData:
            # max size of 5120B, or 5 KiB
            length = reader.readVarInt()
            for i in range(0, length):
                d = reader.readByte()
                cookieData.append(d)
        
        shs = ServerHandleResponse()
        shs.type = "CookieResponse"
        shs.cookieKey = key
        shs.cookieData = cookieData
        return shs


# Extra classes
class HandleResponse:
    def __init__(self):
        # connection updates
        self.respondWithPackets: list[Packet] = []
        self.nextConnectionState: ConnectionState = None

        # update client specific values
        self.updateUsername: str = None
        self.updateUUID: bytes = None
        self.updatePosition: tuple[float, float, float] = None # x, y, z
        self.updateRotation: tuple[float, float] = None # yaw, pitch
        self.updateOnGround: bool = None
        self.updateAgainstWall: bool = None
        self.updateSprinting: bool = None
        self.updateElytraGliding: bool = None
        self.updateFlying: bool = None

        # client todo flags:
        self.sendLoginFinishedPacket = False
        self.generateAndSendRegistryData = False
        self.clientLoginToWorld = None

        # Info to know that something did happen
        self.teleportId: int = None

class ServerHandleResponse:
    def __init__(self):
        self.type: str = None
        self.fromClientEID: int = None
        
        # swing
        self.swingHand: bool = None # None = not used, False = offhand, True = main hand
        # attack
        self.swingEntityId: int = None
        # changeDifficulty
        self.difficulty: DIFFICULTY = None
        self.difficultyLocked: bool = None
        # changeGamemode
        self.gamemode: GAMEMODE = None
        # chat
        self.message: str = None
        self.timestamp: int = None
        self.messageSalt: int = None
            # there are more fields ive not passed here. signature, msg count, acknowledged, checksum
        # client command (client status)
        self.actionId: ACTION_ID = None
        # containerButtonClick
        self.windowId: int = None
        self.buttonId: int = None
        # containerClick
        self.stateId: int = None
        self.slot: int = None
        self.button: int = None
        self.mode: int = None
        self.arrOfChangedSlots: dict[int, None] = None # todo: make this a dict of {slot num: hashed slot data}
        self.carriedItem = None # todo: make this a hashed slot
        # containerSlotStateChanged
        self.slotId: int = None
        self.slotState: bool = None
        # cookieResponse
        self.cookieKey: str = None
        self.cookieData: list[int] = None


# Decoding and other packet stuff

HANDSHAKING_PACKETS = [Intention_ServerBound]
STATUS_PACKETS = [
    StatusRequest_ServerBound,
    PingRequest_ServerBound,
]
LOGIN_PACKETS = [
    Hello_ServerBound,
    LoginAcknowledged_ServerBound,
]
CONFIGURATION_PACKETS = [
    ClientInformation_ServerBound,
    FinishConfiguration_ServerBound,
    CustomPayload_ServerBound,
]
PLAY_PACKETS = [
    PlayerLoaded_ServerBound, ClientTickEnd_ServerBound,

    # position
    AcceptTeleportation_ServerBound,
    MovePlayerPosRot_ServerBound, MovePlayerPos_ServerBound, MovePlayerRot_ServerBound, MovePlayerStatusOnly_ServerBound,

    # Server setting stuff
    ChangeDifficulty_ServerBound,
    ChangeGamemode_ServerBound,

    # activities
    Swing_ServerBound, Attack_ServerBound,

    PlayerInput_ServerBound, PlayerCommand_ServerBound, PlayerAbilities_ServerBound,
    PlayerAction_ServerBound,
    ClientCommand_ServerBound,
    
    ContainerButtonClick_ServerBound, ContainerClick_ServerBound, ContainerSlotStateChanged_ServerBound,
    
    ChatAck_ServerBound,
    Chat_ServerBound,

    # misc
    Pong_ServerBound,
    KeepAlive_ServerBound,
    
    # config
    ConfigurationAcknowledge_ServerBound,
]

def decodePacket(data: bytes, connState: ConnectionState) -> tuple[bytes, Packet]:
    reader = PacketDataReader(data)
    if len(data) <= 0: return (data, None) # No bytes... We can't do anything with that!
    
    packetLength = reader.readVarInt()
    if len(reader) < packetLength: return (data, None) # We haven't read in enough bytes from the socket for this full packet!
    
    packetId = reader.readVarInt()
    dataBytes: bytes = reader.readNBytes(packetLength-1) # -1 b/c the packetId is included in the length
    
    packet: Packet = None
    packetClasses = []
    
    if connState == "HANDSHAKING": packetClasses = HANDSHAKING_PACKETS
    elif connState == "STATUS": packetClasses = STATUS_PACKETS
    elif connState == "LOGIN": packetClasses = LOGIN_PACKETS
    elif connState == "CONFIGURATION": packetClasses = CONFIGURATION_PACKETS
    elif connState == "PLAY": packetClasses = PLAY_PACKETS

    for packetType in packetClasses:
        packet = packetType(dataBytes)
        if (packet.boundDirection != "ServerBound") or (packet.id != packetId):
            # Either we're not server bound or the packet IDs don't match up! Either way it's the wrong packet
            packet = None # make sure we clear the packet else it could lead to a false positive
            continue
        break # all good, break to continue

    if packet == None:
        packetId = "0x" + (hex(packetId).split("0x")[1]).zfill(2)
        print(f"{textColors.RED}Unknown packet state and or id! {packetId=} {connState=}{textColors.RESET}")

    return (reader.data, packet)

def printCompletionOfPackets():
    allPackets: dict[str, dict[str,dict[str,int]]] = None # protocol: {cb/sb: {name: {protocol_id: id}}}
    targetPacketsFilePath = f"{Registry.reportsPath}/packets.json"
    with open(targetPacketsFilePath, "r") as f:
        allPackets = json.load(f)
    if allPackets == None:
        print(f"{textColors.RED}Unable to load target packet info from '{targetPacketsFilePath}'{textColors.RESET}")
        return
    
    parts = ["handshake", "status", "login", "configuration", "play"]
    partToList = {"handshake": HANDSHAKING_PACKETS, "status": STATUS_PACKETS, "login": LOGIN_PACKETS, "configuration": CONFIGURATION_PACKETS, "play": PLAY_PACKETS}
    
    print(f"{textColors.BLUE}Serverbound packet completeness test:{textColors.RESET}")
    for p in parts:
        keys = list(allPackets[p]["serverbound"].keys())
        implementedList = partToList[p]
        
        percent = len(implementedList)/len(keys)
        # 75%-100% = green, 50%-75%=yellow 0%-50%=red
        prefix = textColors.GREEN if percent>=0.75 else (textColors.YELLOW if percent>=0.50 else textColors.RED)
        print(f" -> {prefix}{p.capitalize()} packets | {len(implementedList)}/{len(keys)} = {(percent)*100:.2f}%{textColors.RESET}")
        
        onesWeHave = []
        for packetClass in implementedList:
            pCls = packetClass()
            onesWeHave.append(f"minecraft:{pCls.name}")
        
        for packetName in keys:
            isX = "x" if packetName in onesWeHave else ""
            text = f"      [{isX}] {packetName.split(':')[1]}"
            print(text)

    
    

