import time
from typing import Literal, TYPE_CHECKING
import math
import threading
import random

from dataTypes import PacketDataReader, PacketDataWriter
from ServerSettings import ServerSettings
import packets
from enumValues import *
from RegionFiles import Region, Chunk
from Registry import Registry, TagsPacketForSyncedRegistry
from Entity import Entity
if TYPE_CHECKING: from client import Client # import only for type checking



class World:
    players: dict[int, Client] = {} # player eid, client class (which is a subclass of the entity class)
    entities: dict[int, Entity] = {} # entity id, entity object
    regions: dict[str, Region] = {} # filename (ex. r.0.0.mca), object that has it loaded

    seed: int = 0
    time: int = 0 # time in ticks, time % 24000 -> 0=sunrise, 6000=noon, 12000=sunset, and 18000=midnight

    tickRate: float = 20 # 20 tps
    isTickFrozen: bool = False

    renderDistance: int = 16
    simulationDistance: int = 8 

    difficulty: DIFFICULTY = "PEACEFUL"
    difficultyLocked: bool = False

    defaultGameMode: GAMEMODE = "SURVIVAL"
    isHardcore: bool = False

    worldSeaLevel: int = 60
    worldBorder: dict[str, float] = {"centerX": 0, "centerZ": 0, "diameter": 1_000_000, "warningBlocks": 0}
    worldSpawn: dict[str, float] = {"dimension": "minecraft:overworld", "x": 0, "y": 60, "z": 0, "yaw": 0, "pitch": 0}

    worldName: str = "world"

    nextEntityId: int = 1
    @classmethod
    def allocateEntityId(cls) -> int:
        eid = cls.nextEntityId
        cls.nextEntityId += 1
        return eid

    @classmethod
    def loadRegionFile(cls, fileName: str, overwrite: bool = False):
        old = cls.regions.get(fileName, None)
        if old == None or overwrite==True:
            cls.regions[fileName] = Region(fileName)
        else:
            pass # will not overwrite already opened region file, consider closing it first (need to make that function)

    @classmethod
    def loadRegionFileFromChunkCoords(cls, chunkX: int, chunkZ: int, overwrite: bool=False):
        regionX = chunkX // 32
        regionZ = chunkZ // 32
        regionFileName = f"./{cls.worldName}/overworld/r.{regionX}.{regionZ}.mca"
        cls.loadRegionFile(regionFileName, overwrite)

    @classmethod
    def getRegion(cls, fileName: str) -> Region:
        return cls.regions.get(fileName, None)

    @classmethod
    def getRegionFromChunkCoords(cls, chunkX: int, chunkZ: int) -> Region:
        regionX = chunkX // 32
        regionZ = chunkZ // 32
        regionFileName = f"./world/overworld/r.{regionX}.{regionZ}.mca"
        return cls.getRegion(regionFileName)
    

    @classmethod
    def onPlayerJoin(cls, client: Client):
        client.gamemode = cls.defaultGameMode
        cls.players[client.entityId] = client
        ServerSettings.playersOnline = len(cls.players.keys())

        # login packet
        playData = PacketDataWriter()
        playData.writeInt(client.entityId) # player entity id, EID
        playData.writeBoolean(cls.isHardcore) # is hardcore
        playData.writeVarInt(3) # all dimension names, 3 for how many dimension names we're giving
        playData.writeIdentifier("minecraft:overworld")
        playData.writeIdentifier("minecraft:nether")
        playData.writeIdentifier("minecraft:the_end")
        playData.writeVarInt(0) # max players, used to draw tablist but now ignored
        playData.writeVarInt(cls.renderDistance) # render distance (2-32)
        playData.writeVarInt(cls.simulationDistance) # simulation dist
        playData.writeBoolean(False) # reduced debug info (false for development)
        playData.writeBoolean(ServerSettings.gameRules.doImmediateRespawn==False) # enable respawn screen
        playData.writeBoolean(ServerSettings.gameRules.doLimitedCrafting) # do limited crafting (unused by client)
        playData.writeVarInt( Registry.getSyncedRegistry("minecraft:dimension_type").getEntryIndex(f"minecraft:{client.dimension}") ) # dimension type
        playData.writeIdentifier(f"minecraft:{client.dimension}") # dimension name
        playData.writeLong(0) # hashed seed, first 8 bytes of it TODO make it take cls.seed and hash it and shi
        playData.writeUnsignedByte(GAMEMODE_Enum[client.gamemode]) # game mode
        playData.writeByte(GAMEMODE_Enum["NULL"]) # previous gamemode, used for F3+F4. Same as above just -1 is null
        playData.writeBoolean(False) # is debug world
        playData.writeBoolean(False) # is superflat world
        playData.writeBoolean(False) # has death location. makes the next 2 fields present
        #playData.writeIdentifier("minecraft:overworld") # last death dimension name
        #playData.writePosition(fill it out here) # last death pos
        playData.writeVarInt(0) # portal cooldown in ticks
        playData.writeVarInt(cls.worldSeaLevel) # sea level
        playData.writeBoolean(False) # online mode
        playData.writeBoolean(False) # enforces secure chat
        playPacket = packets.Login_ClientBound(playData)

        # change difficulty packet
        changeDiffData = PacketDataWriter()
        changeDiffData.writeUnsignedByte( DIFFICULTY_Enum[cls.difficulty] )
        changeDiffData.writeBoolean(cls.difficultyLocked)
        changeDiffPacket = packets.ChangeDifficulty_ClientBound(changeDiffData)

        # player abilities packet
        # flagsVal |= 0x1 # if player is invulnerable
        # flagsVal |= 0x2 # if player is flying
        # flagsVal |= 0x4 # if player is allowed to fly
        # flagsVal |= 0x8 # for "creative mode" (instant break blocks)
        abilitiesFlagsVal = 0
        if client.isInvulnerable: abilitiesFlagsVal |= 0x1
        if client.isFlying: abilitiesFlagsVal |= 0x2
        if client.isAllowedToFly: abilitiesFlagsVal |= 0x4
        if client.canInstaBreakBlocks: abilitiesFlagsVal |= 0x8

        playerAbilitiesData = PacketDataWriter()
        playerAbilitiesData.writeByte(abilitiesFlagsVal)
        playerAbilitiesData.writeFloat(0.05) # flying speed (default = 0.05)
        playerAbilitiesData.writeFloat(0.1) # fov modifier (default is 0.1?) check https://minecraft.wiki/w/Java_Edition_protocol/Packets#Player_Abilities_(clientbound)
        playerAbilitiesPacket = packets.PlayerAbilities_ClientBound(playerAbilitiesData)

        # set held item packet
        heldSlotData = PacketDataWriter()
        heldSlotData.writeVarInt(0) # slow which the player has selected (0-8)
        heldSlotPacket = packets.SetHeldSlot_ClientBound(heldSlotData)

        # update recipes packet
        
        # entity event packet | for the OP permission level
        entityEventData = PacketDataWriter()
        entityEventData.writeInt( client.entityId ) # Entity ID
        entityEventData.writeByte(24 + client.opLevel) # 24->28 = op level 0->4 respectivly
        entityEventPacket = packets.EntityEvent_ClientBound(entityEventData)

        # commands packet
        
        # update recipe book packet
        
        # synchronize player position packet
        ppcbData: bytes = PacketDataWriter()
        client.teleportId += 1
        ppcbData.writeVarInt(client.teleportId) # teleport id, will be used to confirm in confirm teleport packet
        ppcbData.writeDouble(client.posX) # X
        ppcbData.writeDouble(client.posY) # Y
        ppcbData.writeDouble(client.posZ) # Z
        ppcbData.writeDouble(client.velX) # Vx
        ppcbData.writeDouble(client.velY) # Vy
        ppcbData.writeDouble(client.velZ) # Vz
        ppcbData.writeFloat(client.yaw) # yaw, in degrees
        ppcbData.writeFloat(client.pitch) # pitch, in degrees
        ppcbData.writeInt(0) # teleport flags (https://minecraft.wiki/w/Java_Edition_protocol/Packets#Teleport_Flags)
        ppcb = packets.PlayerPosition_ClientBound(ppcbData)

        # server data (the MOTD and icon)
        
        # player info update (https://minecraft.wiki/w/Java_Edition_protocol/Packets#player-info:player-actions)
        piuActionsFlag = 0x00
        piuInfoActions = ["AddPlayer", "UpdateGameMode", "UpdateListed", "UpdateLatency", "UpdateListPriority", "UpdateHat"]
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
        piuData.writeVarInt( len(cls.players.keys()) )
        for player in cls.players.values():
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
                pass # idk how to work with TextComponents so ill skip it for now
            if piuActionsFlag & 0x40 == 0x40:
                # List priority
                piuData.writeVarInt(0)
            if piuActionsFlag & 0x80 == 0x80:
                # is hat visible
                piuData.writeBoolean(True) # true for now, why not

        piuPacket = packets.PlayerInfoUpdate_ClientBound(piuData)

        # init world border
        initWBData = PacketDataWriter()
        initWBData.writeDouble(cls.worldBorder["centerX"]) # center x
        initWBData.writeDouble(cls.worldBorder["centerZ"]) # center z
        initWBData.writeDouble(cls.worldBorder["diameter"]) # old diameter
        initWBData.writeDouble(cls.worldBorder["diameter"]) # new diameter
        initWBData.writeVarLong(0) # speed
        initWBData.writeVarInt(29999984) # portal teleport boundary, usually 29999984
        initWBData.writeVarInt(cls.worldBorder["warningBlocks"]) # warning blocks, in meters
        initWBData.writeVarInt(0) # warning time, in seconds
        initWBPacket = packets.InitializeBorder_ClientBound(initWBData)

        # update time
        setTimeData = PacketDataWriter()
        setTimeData.writeLong(cls.time) # world age
        setTimeClocks: list[str] = Registry.getSyncedRegistry("minecraft:world_clock").getEntries()
        print("\t\t", setTimeClocks)
        setTimeData.writeVarInt(len(setTimeClocks)) # len of array of Clocks
        for clockRegId, identifier in enumerate(setTimeClocks):
            setTimeData.writeVarInt(clockRegId) # clock registry id
            setTimeData.writeVarLong(cls.time) # current time of the clock
            setTimeData.writeFloat(0) # fractional part of the time in ticks (non-negative num less than 1)
            setTimeData.writeFloat(1) # rate, in clock tick per client tick
        setTimePacket = packets.SetTime_ClientBound(setTimeData)
        # sending the time at 24000+ seems to auto modulos so we don't have to do it
        
        # set default spawn location (optional, "home" spawn,,, not where client will spawn in)
        defaultSpawnData = PacketDataWriter()
        defaultSpawnData.writeIdentifier(cls.worldSpawn["dimension"]) # dimension
        defaultSpawnData.writePosition(cls.worldSpawn["x"], cls.worldSpawn["y"], cls.worldSpawn["z"]) # pos
        defaultSpawnData.writeFloat(cls.worldSpawn["yaw"]) # yaw
        defaultSpawnData.writeFloat(cls.worldSpawn["pitch"]) # pitch
        defaultSpawnPacket = packets.SetDefaultSpawnPosition_ClientBound(defaultSpawnData)

        # game event (for telling the client to wait for chunks)
        gameEventData = PacketDataWriter()
        gameEventData.writeUnsignedByte(13) # event id, 13=start waiting for level chunks
        gameEventData.writeFloat(0) # I don't think "start waiting for level chunks" needs this but ill put it here just in case
        gameEventPacket = packets.GameEvent_ClientBound(gameEventData)

        # set ticking state (sets the tickrate and if its frozen or not)
        tickingStateData = PacketDataWriter()
        tickingStateData.writeFloat(cls.tickRate) # tick rate
        tickingStateData.writeBoolean(cls.isTickFrozen) # is frozen?
        #tickingStatePacket = packets.TickingState_ClientBound(tickingStateData) # I have no idea why this fucks up the speed of the client's game, no matter the value I put. Im just gonan remove it for rn

        # set center chunk
        playerChunkX = client.posX // 16
        playerChunkZ = client.posZ // 16

        setChunkCenterData = PacketDataWriter()
        setChunkCenterData.writeVarInt(playerChunkX) # chunk x
        setChunkCenterData.writeVarInt(playerChunkZ) # chunk z
        setChunkCenterPacket = packets.SetChunkCacheCenter_ClientBound(setChunkCenterData)

        client.queuedOutboundPackets.extend([
            playPacket,
            changeDiffPacket, playerAbilitiesPacket, heldSlotPacket,
            entityEventPacket,
            ppcb,
            piuPacket, initWBPacket, setTimePacket, defaultSpawnPacket,
            gameEventPacket,
            #tickingStatePacket,
            setChunkCenterPacket
        ])

        # send chunks to player after we've queued the packets above
        #chunkSendThread = threading.Thread(target=cls.sendChunksInView, args=(client,), daemon=True)
        #chunkSendThread.start()

    @classmethod
    def onPlayerLeave(cls, client: Client):
        del cls.players[client.entityId]
        # todo: send a logout packet i guess

    @classmethod
    def sendChunksInView(cls, client: Client):
        # TODO: make the server send a batch chunks thing, then negotiate it, and then queue the chunks outbound in chunks/tick
        playerChunkX = int(client.posX // 16)
        playerChunkZ = int(client.posZ // 16)

        halfRenderDist = 3
        #halfRenderDist = cls.renderDistance//2
        #halfRenderDist = cls.renderDistance

        def sendChunk(client: Client, x: int, z: int):
            chunkX = x
            chunkZ = z
            cls.loadRegionFileFromChunkCoords(chunkX, chunkZ)
            region: Region = cls.getRegionFromChunkCoords(chunkX, chunkZ)

            chunk: Chunk = region.getChunk(chunkX, chunkZ)
            chunkUpdateData = chunk.getChunkPacketData()
            if len(chunkUpdateData) == 0: return # no data to return, probably an unfinished/ungenerated chunk :(
            chunkUpdatePacket = packets.LevelChunkWithLight_ClientBound(chunkUpdateData)
            client.queuedOutboundPackets.append(chunkUpdatePacket)

        # get a list of unloaded chunks
        chunkCoordsToSend = []
        for dx in range(-halfRenderDist, halfRenderDist):
            for dz in range(-halfRenderDist, halfRenderDist):
                x = playerChunkX + dx
                z = playerChunkZ + dz
                if (x,z) in client.loadedChunkCoords: continue # already loaded, skip it
                chunkCoordsToSend.append((x,z))
        # sort it so the closest chunks are started threaded first
        chunkCoordsToSend.sort(key=lambda _: math.dist(_, (playerChunkX, playerChunkZ)))
        
        # load in the new chunks
        for x,z in chunkCoordsToSend:
            print("\t",x,z)
            threadX = threading.Thread(target=sendChunk, args=(client,x,z), daemon=True)
            threadX.start()
        
        client.loadedChunkCoords.extend(chunkCoordsToSend)

    @classmethod
    def sendPacketToPlayer(cls, eid: int, packet: packets.Packet):
        cls.players[eid].queuedOutboundPackets.append(packet)

    @classmethod
    def sendPacketToAllPlayers(cls, packet: packets.Packet):
        for eid in cls.players.keys(): cls.sendPacketToPlayer(eid, packet)

    @classmethod
    def handlePacketReturn(cls, packetResponse: packets.ServerHandleResponse):
        responseType = packetResponse.type
        fromClientEID: int = packetResponse.fromClientEID
        
        if responseType == "swing":
            isMainHand = packetResponse.swingHand
            # TODO: make it announce this to other players
        elif responseType == "attack":
            recvAttackEID = packetResponse.swingEntityId
            print(f"Attacked {recvAttackEID}")
            # TODO: make the receiving entity take damage or something
        elif responseType == "changeDifficulty":
            difficulty: DIFFICULTY = packetResponse.difficulty
            isDifficultyLocked: bool = packetResponse.difficultyLocked
            print(f"Tried to change the difficulty to {difficulty} and {isDifficultyLocked=}")
            # TODO make it change the difficulty if allowed to
        elif responseType == "changeGamemode":
            gamemode: GAMEMODE = packetResponse.gamemode
            print(f"Tried to change gamemode to {gamemode}")
            # TODO make it change the gamemode if allowed to
        elif responseType == "chat":
            message: str = packetResponse.message
            timestamp: int = packetResponse.timestamp
            salt: int = packetResponse.messageSalt
            
            for eid in cls.players.keys():
                plr = cls.players[fromClientEID]
                msgPacket = packets.PlayerChat_ClientBound.write(
                    plr.username,
                    message, timestamp, salt,
                    plr.messagesRecv, plr.messagesSent, plr.UUID
                )
                cls.sendPacketToPlayer(eid, msgPacket)
                plr.messagesRecv += 1
                if eid == fromClientEID: plr.messagesSent += 1
        elif responseType == "ClientCommand":
            actionId: ACTION_ID = packetResponse.actionId
            # TODO: handle this
        elif responseType == "ContainerButtonClick":
            windowId: int = packetResponse.windowId
            buttonId: int = packetResponse.buttonId
            
            # todo: get the player's open container type and process it
        elif responseType == "ContainerClick":
            windowId = packetResponse.windowId
            stateId = packetResponse.stateId
            slot = packetResponse.slot
            button = packetResponse.button
            mode = packetResponse.mode
            arrOfChangedSlots = packetResponse.arrOfChangedSlots
            carriedItem = packetResponse.carriedItem
            
            # todo: implement this
        elif responseType == "ContainerSlotStateChanged":
            slotId = packetResponse.slotId
            windowId = packetResponse.windowId
            slotState = packetResponse.slotState
            
            # todo: this is used only for a crafter. So (un)lock that slot
        elif responseType == "CookieResponse":
            key = packetResponse.cookieKey
            data = packetResponse.cookieData
            
            # todo: uhh idk what we'd do with this. forward this to whatever requested the cookies
        
        pass

    @classmethod
    def run(cls):
        Registry.preloadRequiredSyncedRegistries() # preload the required ones we need
        TagsPacketForSyncedRegistry.init()

        while True:
            if cls.isTickFrozen: continue
            cls.tick()
            time.sleep( 1 / cls.tickRate ) # 1sec per tick

    @classmethod
    def tick(cls):
        cls.time += 1

        # send a keep alive packet every 5 seconds or so
        if cls.time % (5*cls.tickRate) == 0:
            for plr in cls.players.values():
                keepAlivePacket = packets.KeepAlive_ClientBound( random.randbytes(8) ) # 8 bytes for a random long
                plr.queuedOutboundPackets.append(keepAlivePacket)



