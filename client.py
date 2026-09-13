import packets
from dataTypes import PacketDataWriter, PacketDataReader
from ServerSettings import ServerSettings
from world import World
from enumValues import *
from Registry import Registry, TagsPacketForSyncedRegistry
from Entity import Entity

import os
import random
import requests


def getAllSubDirs(basePath: str) -> list[str]:
    baseLen = len(basePath.rstrip(os.sep)) + 1
    subdirs = []

    def _scan(path):
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry.path[baseLen:])
                        _scan(entry.path)
        except PermissionError: pass

    _scan(basePath)
    return subdirs


class Client(Entity):
    def __init__(self):
        super().__init__()
        self.username = ""
        self.setPosition(0, 80, 0) # set the position a bit up for our default player
        
        self.gamemode: GAMEMODE = "NULL"
        self.loadedChunkCoords: list[tuple[int, int]] = []

        #   Movement states
        self.isSprinting = False
        self.isElytraGliding = False
        self.isFlying = False # flying like creative mode, not via elytra

        #   Permissions
        self.isAllowedToFly = True
        self.isInvulnerable = False
        self.canInstaBreakBlocks = False
        self.opLevel = 4 # 0 to 4 inclusive

        self.isUnsignedPlayerPropertiesFromAPI: bool = False
        self.playerPropertiesFromAPI: list[dict[str, str]] = [] # list of properties from the mojang api for our player. eg textures & capes

        # Special numbers that can tick up, keep track of these
        self.setEID( World.allocateEntityId() )
        self.teleportId: int = random.randint(1, 999)
        self.messagesRecv: int = 0
        self.messagesSent: int = 0

        # Connection stuff
        self.state: packets.ConnectionState = "HANDSHAKING"
        self.socketData: bytes = bytes()
        self.unhandledPackets: list[packets.Packet] = []
        self.queuedOutboundPackets: list[packets.Packet] = []

    def handlePacketReturn(self, packetResponse: packets.HandleResponse|packets.ServerHandleResponse):
        if packetResponse == None: return
        # forward it to the world handler
        if type(packetResponse) == packets.ServerHandleResponse:
            packetResponse.fromClientEID = self.entityId
            return World.handlePacketReturn(packetResponse)

        # connection updates
        self.queuedOutboundPackets.extend( packetResponse.respondWithPackets )
        if packetResponse.nextConnectionState != None: self.state = packetResponse.nextConnectionState

        # update the client's data
        if packetResponse.updateUsername != None: self.username = packetResponse.updateUsername
        if packetResponse.updateUUID != None:
            self.setUUID(packetResponse.updateUUID)
            self.generatePlayerPropertiesFromAPI() # now that we have the UUID fetch it's data from mojang servers
            
        if packetResponse.updatePosition != None:
            self.setPosition(*packetResponse.updatePosition)
            World.sendChunksInView(self)
        if packetResponse.updateRotation != None: self.setRotation(*packetResponse.updateRotation)
        if packetResponse.updateOnGround != None: self.onGround = packetResponse.updateOnGround
        if packetResponse.updateAgainstWall != None: pass # dont care abt it rn
        if packetResponse.updateSprinting != None: self.isSprinting = packetResponse.updateSprinting
        if packetResponse.updateElytraGliding != None: self.isElytraGliding = packetResponse.updateElytraGliding
        if packetResponse.updateFlying != None: self.isFlying = packetResponse.updateFlying

        # client todo stuff
        if packetResponse.sendLoginFinishedPacket == True: self.sendLoginFinishedPacket()
        if packetResponse.generateAndSendRegistryData == True:
            self.generateAndSendConfigData()
            self.generateAndSendRegistryData()
        if packetResponse.clientLoginToWorld == True: World.onPlayerJoin(self)
        if packetResponse.clientLoginToWorld == False: World.onPlayerLeave(self)

        # info from packets to know stuff happened
        if packetResponse.teleportId != None:
            if packetResponse.teleportId == self.teleportId:
                print(f"~~~ Teleport (id: {packetResponse.teleportId}) was successful")

    def generatePlayerPropertiesFromAPI(self):
        if self.UUID == None: return

        uuidString = "".join([ hex(b).split("0x")[1].zfill(2) for b in self.UUID ])
        r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuidString}?unsigned={self.isUnsignedPlayerPropertiesFromAPI}")
        self.playerPropertiesFromAPI = r.json()["properties"]

    def getNextPacket(self):
        self.socketData, packet = packets.decodePacket(self.socketData, self.state)
        return packet

    def handlePackets(self):
        while True:
            packet = self.getNextPacket()
            if packet == None: break
            print(packet)
            try:
                response = packet.handle()
                self.handlePacketReturn(response)
            except Exception as e:
                raise e

    def readInBytes(self, newData: bytes):
        self.socketData += newData
        self.handlePackets()

    def getGameProfile(self, ignoreUUID=False) -> bytes:
        out = PacketDataWriter()
        if ignoreUUID == False: out += self.UUID
        out.writeString(self.username)
        out.writeVarInt( len(self.playerPropertiesFromAPI) )
        for property in self.playerPropertiesFromAPI:
            isSigned = not self.isUnsignedPlayerPropertiesFromAPI
            out.writeString(property["name"])
            out.writeString(property["value"])
            out.writeBoolean( isSigned )
            if isSigned: out.writeString(property["signature"])
        return out

    def sendLoginFinishedPacket(self):
        packetData = PacketDataWriter()
        packetData.writeRawBytes(self.getGameProfile())        
        packetData.writeRawBytes(bytes(16)) # Session ID (as a UUID) | I don't think it really matters so im making it all 0s for right now

        self.queuedOutboundPackets.append(packets.LoginFinished_ClientBound(packetData))

    def generateAndSendConfigData(self):
        brandPluginMessageData = PacketDataWriter()
        brandPluginMessageData.writeIdentifier("minecraft:brand")
        brandPluginMessageData.writeString(ServerSettings.serverBrand)
        brandPluginMessagePacket = packets.CustomPayload_ClientBound(brandPluginMessageData)

        featureFlagsData = PacketDataWriter()
        featureFlagsData.writeVarInt(1) # how many identifiers after this?
        featureFlagsData.writeIdentifier("minecraft:vanilla")
        featureFlagsPacket = packets.UpdateEnabledFeatures_ClientBound(featureFlagsData)

        knownDatapacksData = PacketDataWriter()
        knownDatapacksData.writeVarInt(1) # how many datapacks?
        knownDatapacksData.writeString("minecraft") # namespace
        knownDatapacksData.writeString("core") # pathname
        knownDatapacksData.writeString(ServerSettings.version) # version of the pack
        knownDatapacksPacket = packets.SelectKnownPacks_ClientBound(knownDatapacksData)


        self.queuedOutboundPackets.extend([
            brandPluginMessagePacket, featureFlagsPacket, knownDatapacksPacket
        ])

    def generateAndSendRegistryData(self):
        queuedRegisters = Registry._neededSyncedRegistries
        for register in queuedRegisters:
            print(register)
            syncedReg = Registry.getSyncedRegistry(register)
            packetData = syncedReg.getPacketData()
            registryPacket = packets.RegistryData_ClientBound(packetData)
            self.queuedOutboundPackets.append( registryPacket )

        # registry tags
        updateTagsPacketData = TagsPacketForSyncedRegistry.getPacketData()
        updateTagsPacket = packets.UpdateTags_ClientBound(updateTagsPacketData)
        self.queuedOutboundPackets.append(updateTagsPacket)


        finishConfigPacket = packets.FinishConfiguration_ClientBound()
        self.queuedOutboundPackets.append(finishConfigPacket)

