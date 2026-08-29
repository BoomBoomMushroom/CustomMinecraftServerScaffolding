import time
from typing import Literal, TYPE_CHECKING
import math
import threading
import random

import dataTypes
from ServerSettings import ServerSettings
import packets
from enumValues import *
from RegionFiles import Region, Chunk
from Registry import Registry, SyncedRegistry, TagsPacketForSyncedRegistry
if TYPE_CHECKING: from client import Client # import only for type checking



class World:
    players: list[Client] = [] # maybe make a player class instead
    entities: list = []
    regions: dict[str, Region] = {} # filename (ex. r.0.0.mca), object that has it loaded

    seed: int = 0
    time: int = 0 # time in ticks, time % 24000 -> 0=sunrise, 6000=noon, 12000=sunset, and 18000=midnight
    renderDistance: int = 16
    simulationDistance: int = 8 
    difficulty: DIFFICULTY = "PEACEFUL"
    difficultyLocked: bool = False
    defaultGameMode: GAMEMODE = "SURVIVAL"
    worldSeaLevel: int = 60
    worldBorder: dict[str, float] = {"centerX": 0, "centerZ": 0, "diameter": 1_000_000, "warningBlocks": 0}
    worldSpawn: dict[str, float] = {"dimension": "minecraft:overworld", "x": 0, "y": 0, "z": 0, "yaw": 0, "pitch": 0}
    tickRate: float = 20 # 20 tps
    isTickFrozen: bool = False

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
        regionFileName = f"./world/overworld/r.{regionX}.{regionZ}.mca"
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
        cls.players.append(client)
        ServerSettings.playersOnline = len(cls.players)

        # login packet
        playData: bytes = bytes()
        playData += dataTypes.writeInt(client.playerEntityId) # player entity id, EID
        playData += dataTypes.writeBoolean(False) # is hardcore
        playData += dataTypes.writeVarInt(3) # all dimention names, 3 for how many dimention names we're giving
        playData += dataTypes.writeIdentifier("minecraft:overworld")
        playData += dataTypes.writeIdentifier("minecraft:nether")
        playData += dataTypes.writeIdentifier("minecraft:the_end")
        playData += dataTypes.writeVarInt(0) # max players, used to draw tablist but now ignored
        playData += dataTypes.writeVarInt(cls.renderDistance) # render distance (2-32)
        playData += dataTypes.writeVarInt(cls.simulationDistance) # simulation dist
        playData += dataTypes.writeBoolean(False) # reduced debug info (false for development)
        playData += dataTypes.writeBoolean(ServerSettings.gameRules.doImmediateRespawn==False) # enable respawn screen
        playData += dataTypes.writeBoolean(ServerSettings.gameRules.doLimitedCrafting) # do limited crafting (unused by client)
        playData += dataTypes.writeVarInt( Registry.getSyncedRegistry("minecraft:dimension_type").getEntryIndex("minecraft:overworld") ) # dimention type
        playData += dataTypes.writeIdentifier("minecraft:overworld") # dimention name
        playData += dataTypes.writeLong(0) # hashed seed, first 8 bytes of it TODO make it take cls.seed and hash it and shi
        playData += dataTypes.writeUnsignedByte(GAMEMODE_Enum[client.gamemode]) # game mode
        playData += dataTypes.writeByte(-1) # previous gamemode, used for F3+F4. Same as above just -1 is null
        playData += dataTypes.writeBoolean(False) # is debug world
        playData += dataTypes.writeBoolean(False) # is superflat world
        playData += dataTypes.writeBoolean(False) # has death location. makes the next 2 fields present
        #playData += dataTypes.writeIdentifier("minecraft:overworld") # last death dimention name
        #playData += dataTypes.writePosition(fill it out here) # last death pos
        playData += dataTypes.writeVarInt(0) # portal cooldown in ticks
        playData += dataTypes.writeVarInt(cls.worldSeaLevel) # sea level
        playData += dataTypes.writeBoolean(False) # online mode
        playData += dataTypes.writeBoolean(False) # enforces secure chat
        playPacket = packets.Login_ClientBound(playData)

        # change difficulty packet
        changeDiffData = bytes()
        changeDiffData += dataTypes.writeUnsignedByte( DIFFICULTY_Enum[cls.difficulty] )
        changeDiffData += dataTypes.writeBoolean(cls.difficultyLocked)
        changeDiffPacket = packets.ChangeDifficulty_ClientBound(changeDiffData)

        # player abilities packet
        playerAbilitiesData = bytes()
        abilitiesFlagsVal = 0 | 0x2 | 0x4
        # flagsVal |= 0x1 # if player is invulnurable
        # flagsVal |= 0x2 # if player is flying
        # flagsVal |= 0x4 # if player is allowed to fly
        # flagsVal |= 0x8 # for "creative mode" (instant break blocks)
        playerAbilitiesData += dataTypes.writeByte(abilitiesFlagsVal)
        playerAbilitiesData += dataTypes.writeFloat(0.05) # flying speed (default = 0.05)
        playerAbilitiesData += dataTypes.writeFloat(0.1) # fov modifier (default is 0.1?) check https://minecraft.wiki/w/Java_Edition_protocol/Packets#Player_Abilities_(clientbound)
        playerAbilitiesPacket = packets.PlayerAbilities_ClientBound(playerAbilitiesData)

        # set held item packet
        heldSlotData = bytes()
        heldSlotData += dataTypes.writeVarInt(0) # slow which the player has selected (0-8)
        heldSlotPacket = packets.SetHeldSlot_ClientBound(heldSlotData)

        # update recipes packet
        
        # entity event packet | for the OP permission level
        entityEventData = bytes()
        entityEventData += dataTypes.writeInt( client.playerEntityId ) # Entity ID
        entityEventData += dataTypes.writeByte(28) # 24->28 = op level 0->4 respectivly
        entityEventPacket = packets.EntityEvent_ClientBound(entityEventData)

        # commands packet
        
        # update recipe book packet
        
        # syncronize player position packet
        ppcbData: bytes = bytes()
        client.teleportId += 1
        ppcbData += dataTypes.writeVarInt(client.teleportId) # teleport id, will be used to confirm in confirm teleport packet
        ppcbData += dataTypes.writeDouble(client.posX) # X
        ppcbData += dataTypes.writeDouble(client.posY) # Y
        ppcbData += dataTypes.writeDouble(client.posZ) # Z
        ppcbData += dataTypes.writeDouble(client.velX) # Vx
        ppcbData += dataTypes.writeDouble(client.velY) # Vy
        ppcbData += dataTypes.writeDouble(client.velZ) # Vz
        ppcbData += dataTypes.writeFloat(client.yaw) # yaw, in degrees
        ppcbData += dataTypes.writeFloat(client.pitch) # pitch, in degrees
        ppcbData += dataTypes.writeInt(0) # teleport flags (https://minecraft.wiki/w/Java_Edition_protocol/Packets#Teleport_Flags)
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

        piuData = bytes()
        piuData += dataTypes.writeUnsignedByte(piuActionsFlag)
        piuData += dataTypes.writeVarInt( len(cls.players) )
        for player in cls.players:
            piuData += player.UUID
            # MUST be in this order im like 99.9% certain of it
            if piuActionsFlag & 0x01 == 0x01:
                # Add player
                piuData += player.getGameProfile(ignoreUUID=True)
            if piuActionsFlag & 0x02 == 0x02:
                # Init chat
                pass # gonna skip this one since im not doing chat encryption right now
            if piuActionsFlag & 0x04 == 0x04:
                # Game Mode
                piuData += dataTypes.writeVarInt( GAMEMODE_Enum[player.gamemode] )
            if piuActionsFlag & 0x08 == 0x08:
                # Listed in tab list
                piuData += dataTypes.writeBoolean(True)
            if piuActionsFlag & 0x10 == 0x10:
                # Ping in ms
                piuData += dataTypes.writeVarInt(0)
            if piuActionsFlag & 0x20 == 0x20:
                # Display name
                pass # idk how to work with TextComponents so ill skip it for now
            if piuActionsFlag & 0x40 == 0x40:
                # List priority
                piuData += dataTypes.writeVarInt(0)
            if piuActionsFlag & 0x80 == 0x80:
                # is hat visible
                piuData += dataTypes.writeBoolean(True) # true for now, why not

        piuPacket = packets.PlayerInfoUpdate_ClientBound(piuData)

        # init world border
        initWBData = bytes()
        initWBData += dataTypes.writeDouble(cls.worldBorder["centerX"]) # center x
        initWBData += dataTypes.writeDouble(cls.worldBorder["centerZ"]) # center z
        initWBData += dataTypes.writeDouble(cls.worldBorder["diameter"]) # old diameter
        initWBData += dataTypes.writeDouble(cls.worldBorder["diameter"]) # new diameter
        initWBData += dataTypes.writeVarLong(0) # speed
        initWBData += dataTypes.writeVarInt(29999984) # portal teleport boundary, usually 29999984
        initWBData += dataTypes.writeVarInt(cls.worldBorder["warningBlocks"]) # warning blocks, in meters
        initWBData += dataTypes.writeVarInt(0) # warning time, in seconds
        initWBPacket = packets.InitializeBorder_ClientBound(initWBData)

        # update time
        setTimeData = bytes()
        setTimeData += dataTypes.writeLong(cls.time) # world age
        setTimeClocks: list[str] = Registry.getSyncedRegistry("minecraft:world_clock").getEntries()
        print("\t\t", setTimeClocks)
        setTimeData += dataTypes.writeVarInt(len(setTimeClocks)) # len of array of Clocks
        for clockRegId, identifier in enumerate(setTimeClocks):
            setTimeData += dataTypes.writeVarInt(clockRegId) # clock registry id
            setTimeData += dataTypes.writeVarLong(cls.time) # current time of the clock
            setTimeData += dataTypes.writeFloat(0) # fractional part of the time in ticks (non-negative num less than 1)
            setTimeData += dataTypes.writeFloat(1) # rate, in clock tick per client tick
        setTimePacket = packets.SetTime_ClientBound(setTimeData)
        # TODO, check sending the time at 24000+ to see if the client handles it and auto modulos it or if we have to in the varlong
        
        # set default spawn location (optional, "home" spawn,,, not where client will spawn in)
        defaultSpawnData = bytes()
        defaultSpawnData += dataTypes.writeIdentifier("minecraft:overworld") # dimension
        defaultSpawnData += dataTypes.writePosition(0, 60, 0) # pos
        defaultSpawnData += dataTypes.writeFloat(0) # yaw
        defaultSpawnData += dataTypes.writeFloat(0) # pitch
        defaultSpawnPacket = packets.SetDefaultSpawnPosition_ClientBound(defaultSpawnData)

        # game event (for telling the client to wait for chunks)
        gameEventData = bytes()
        gameEventData += dataTypes.writeUnsignedByte(13) # event id, 13=start waiting for level chunks
        gameEventData += dataTypes.writeFloat(0) # I don't think "start waiting for level chunks" needs this but ill put it here just in case
        gameEventPacket = packets.GameEvent_ClientBound(gameEventData)

        # set ticking state (sets the tickrate and if its frozen or not)
        tickingStateData = bytes()
        tickingStateData += dataTypes.writeFloat(cls.tickRate) # tick rate
        tickingStateData += dataTypes.writeBoolean(False) # is frozen?
        #tickingStatePacket = packets.TickingState_ClientBound(tickingStateData) # I have no idea why this fucks up the speed of the client's game, no matter the value I put. Im just gonan remove it for rn

        # set center chunk
        playerChunkX = client.posX // 16
        playerChunkZ = client.posZ // 16

        setChunkCenterData = bytes()
        setChunkCenterData += dataTypes.writeVarInt(playerChunkX) # chunk x
        setChunkCenterData += dataTypes.writeVarInt(playerChunkZ) # chunk z
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
        chunkSendThread = threading.Thread(target=cls.sendChunksInView, args=(client,), daemon=True)
        chunkSendThread.start()

    @classmethod
    def sendChunksInView(cls, client: Client):
        playerChunkX = client.posX // 16
        playerChunkZ = client.posZ // 16

        halfRenderDist = cls.renderDistance//2
        #halfRenderDist = cls.renderDistance

        def sendChunk(client: Client, x: int, z: int):
            chunkX = playerChunkX + x
            chunkZ = playerChunkZ + z
            cls.loadRegionFileFromChunkCoords(chunkX, chunkZ)
            region: Region = cls.getRegionFromChunkCoords(chunkX, chunkZ)

            chunk: Chunk = region.getChunk(chunkX, chunkZ)
            chunkUpdateData = chunk.getChunkPacketData()
            chunkUpdatePacket = packets.LevelChunkWithLight_ClientBound(chunkUpdateData)
            client.queuedOutboundPackets.append(chunkUpdatePacket)

        for x in range(-halfRenderDist, halfRenderDist):
            for z in range(-halfRenderDist, halfRenderDist):
                threadX = threading.Thread(target=sendChunk, args=(client,x,z), daemon=True)
                threadX.start()

    @classmethod
    def sendPacketToAllPlayers(cls, packet: packets.Packet):
        for p in cls.players: p.queuedOutboundPackets.append(packet)

    @classmethod
    def run(cls):
        Registry.preloadRequriedSyncedRegistries() # preload the required ones we need
        TagsPacketForSyncedRegistry.init()

        while True:
            if cls.isTickFrozen: continue
            cls.tick()
            time.sleep( 1 / cls.tickRate ) # 1sec per tick

    @classmethod
    def tick(cls):
        cls.time += 1

        # TODO: make the ping packet into a keepalive packet, thats what the vanilla server uses
        # send a ping packet ( https://minecraft.wiki/w/Java_Edition_protocol/Packets#Ping ) every 5 seconds or so
        if cls.time % (5*cls.tickRate) == 0:
            for plr in cls.players:
                keepAlivePacket = packets.KeepAlive_ClientBound( random.randbytes(8) ) # 8 bytes for a random long
                plr.queuedOutboundPackets.append(keepAlivePacket)

        if cls.time % 5 == 0:
            bid = Registry.getRegistryData("minecraft:block", "minecraft:stone")
            bu = bytes()
            bu += dataTypes.writePosition(18, 64, 18)
            bu += dataTypes.writeVarInt(bid)
            buPacket = packets.BlockUpdate_ClientBound(bu)
            #cls.sendPacketToAllPlayers(buPacket)



