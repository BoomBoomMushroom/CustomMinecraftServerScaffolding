import time
from typing import Literal, TYPE_CHECKING
import math

import dataTypes
from ServerSettings import ServerSettings
import packets
from enumValues import *
from RegionFiles import Region, Chunk
if TYPE_CHECKING: from client import Client # import only for type checking



class World:
    players: list[Client] = [] # maybe make a player class instead
    entities: list = []
    regions: dict[str, Region] = {} # filename (ex. r.0.0.mca), object that has it loaded

    seed: int = 0
    time: int = 0 # time in ticks, time % 24000 -> 0=sunrise, 6000=noon, 12000=sunset, and 18000=midnight
    renderDistance: int = 32
    simulationDistance: int = 16 
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
        playData += dataTypes.writeVarInt( client.getRegistryData("minecraft:dimension_type", "minecraft:overworld") ) # dimention type
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
        setTimeClocks: list[str] = client.getRegistryNamespaceList("minecraft:world_clock")
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
        setChunkCenterData = bytes()
        setChunkCenterData += dataTypes.writeVarInt( client.posX//16 ) # chunk x
        setChunkCenterData += dataTypes.writeVarInt( client.posZ//16 ) # chunk z
        setChunkCenterPacket = packets.SetChunkCacheCenter_ClientBound(setChunkCenterData)



        # chunk data & update light (1 for each chunk to load)
        regionX = (client.posX//16) // 32
        regionZ = (client.posZ//16) // 32
        regionFileName = f"./world/overworld/r.{regionX}.{regionZ}.mca"
        cls.loadRegionFile(regionFileName)
        chunkNbt = cls.regions[regionFileName].getChunkNBT( client.posX//16, client.posZ//16 )
        chunkHeightmaps: list[tuple[str, list[int]]] = []
        for key in chunkNbt["Heightmaps"]:
            # these keys below are the only ones the wiki displays w/ it's id so the only ones im sending
            if key not in ["WORLD_SURFACE", "MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES"]: continue
            hmap = chunkNbt["Heightmaps"][key]
            chunkHeightmaps.append((key, hmap))

        
        chunkUpdateData = bytes()
        chunkUpdateData += dataTypes.writeInt(client.posX//16) # chunk x
        chunkUpdateData += dataTypes.writeInt(client.posZ//16) # chunk z

        chunkUpdateData += dataTypes.writeVarInt(len(chunkHeightmaps)) # length of heightmap array
        for hmap in chunkHeightmaps:
            chunkUpdateData += dataTypes.writeVarInt( HEIGHTMAP_TYPE_Enum[hmap[0]] ) # type of heightmap
            chunkUpdateData += dataTypes.writeVarInt(len(hmap[1])) # length of long array
            for long in hmap[1]: chunkUpdateData += dataTypes.writeLong(long) # the longs IN the array
        
        for _,section in enumerate(chunkNbt["sections"]):
            # TODO: maybe make this accurately reflect what it should be? who knows
            chunkUpdateData += dataTypes.writeShort(1) # block count (client keeps tracks of block places and breaks, and if the count hits 0 the chunk stops being rendered)
            chunkUpdateData += dataTypes.writeShort(0) # fluid count
            

            def writePalettedContainer(
                    refName:str, namespace:str, isStaticReg:bool, needToUseNameProperty:bool=False,
                    minBits:int=4, maxBits:int=8,
                ):
                containerBytes = bytes()
                palette = section[refName]["palette"]
                bitsMin = math.floor(math.log2(len(palette)))
                chunkUpdatesBitsPerBlock = min(max(bitsMin,minBits),maxBits)

                getRegFunc = None
                if isStaticReg: getRegFunc = ServerSettings.getRegistryData
                else: getRegFunc = client.getRegistryData

                # if 0 then it is all one block and we just say that
                if bitsMin == 0:
                    containerBytes += dataTypes.writeUnsignedByte(0) # bits per entry, 0=single valued
                    paletteItemName = palette[0]
                    if needToUseNameProperty: paletteItemName = paletteItemName["Name"]
                    containerBytes += dataTypes.writeVarInt( getRegFunc(namespace, str(paletteItemName)) )
                else:
                    # Copy and paste the palette and the blocks list into the packet
                    containerBytes += dataTypes.writeUnsignedByte(chunkUpdatesBitsPerBlock) # bits per entry
                    containerBytes += dataTypes.writeVarInt(len(palette))
                    for paletteItem in palette:
                        if needToUseNameProperty: paletteItem = paletteItem["Name"]
                        blockNum = getRegFunc(namespace, str(paletteItem))
                        containerBytes += dataTypes.writeVarInt(blockNum)

                    blocks = section["block_states"]["data"]
                    for long in blocks: containerBytes += dataTypes.writeLong(long)

                return containerBytes

            chunkUpdateData += writePalettedContainer("block_states", "minecraft:block", isStaticReg=True, needToUseNameProperty=True)
            chunkUpdateData += writePalettedContainer("biomes", "minecraft:worldgen/biome", isStaticReg=False, minBits=1, maxBits=3)
         
        chunkUpdateData += dataTypes.writeVarInt(0) # we're not gonna send block entities here
        # temp light data of all 0s
        chunkUpdateData += dataTypes.writeVarInt(0)
        chunkUpdateData += dataTypes.writeVarInt(0)
        chunkUpdateData += dataTypes.writeVarInt(0)
        chunkUpdateData += dataTypes.writeVarInt(0)
        chunkUpdateData += dataTypes.writeVarInt(0)
        chunkUpdateData += dataTypes.writeVarInt(0)

        chunk: Chunk = cls.regions[regionFileName].getChunk(0, 0)
        chunkUpdateData = chunk.getChunkPacketData()
        chunkUpdatePacket = packets.LevelChunkWithLight_ClientBound(chunkUpdateData)


        client.queuedOutboundPackets.extend([
            playPacket,
            changeDiffPacket, playerAbilitiesPacket, heldSlotPacket,
            entityEventPacket,
            ppcb,
            piuPacket, initWBPacket, setTimePacket, defaultSpawnPacket,
            gameEventPacket,
            #tickingStatePacket,
            setChunkCenterPacket,
            chunkUpdatePacket
        ])

    @classmethod
    def sendPacketToAllPlayers(cls, packet: packets.Packet):
        for p in cls.players: p.queuedOutboundPackets.append(packet)

    @classmethod
    def run(cls):
        while True:
            if cls.isTickFrozen: continue
            cls.tick()
            time.sleep( 1 / cls.tickRate ) # 1sec per tick

    @classmethod
    def tick(cls):
        cls.time += 1

        # send a ping packet ( https://minecraft.wiki/w/Java_Edition_protocol/Packets#Ping ) every 5 seconds or so
        if cls.time % (5*cls.tickRate) == 0:
            pingPacket = packets.Ping_ClientBound( dataTypes.writeInt(0) ) # 0 id for rn
            for plr in cls.players: plr.queuedOutboundPackets.append(pingPacket)

        if cls.time % 20 == 0:
            bid = ServerSettings.getRegistryData("minecraft:block", "minecraft:stone")
            bu = bytes()
            bu += dataTypes.writePosition(0, 55, 0)
            bu += dataTypes.writeVarInt(bid)
            buPacket = packets.BlockUpdate_ClientBound(bu)
            #cls.sendPacketToAllPlayers(buPacket)



        
