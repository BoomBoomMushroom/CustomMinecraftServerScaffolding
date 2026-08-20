import time
from typing import Literal, TYPE_CHECKING

import dataTypes
from ServerSettings import ServerSettings
import packets
from enumValues import *
if TYPE_CHECKING: from client import Client # import only for type checking



class World:
    players: list[Client] = [] # maybe make a player class instead
    entities: list = []

    seed: int = 0
    time: int = 0 # time in ticks
    difficulty: DIFFICULTY = "PEACEFUL"
    difficultyLocked: bool = False
    defaultGameMode: GAMEMODE = "SURVIVAL"
    worldSeaLevel: int = 60
    worldBorder: dict[str, float] = {"centerX": 0, "centerY": 0, "diameter": 1_000_000, "warningBlocks": 0}
    worldSpawn: dict[str, float] = {"dimension": "minecraft:overworld", "x": 0, "y": 0, "z": 0, "yaw": 0, "pitch": 0}
    tickRate: float = 20 # 20 tps
    isTickFrozen: bool = False

    worldName: f"world"


    @classmethod
    def onPlayerJoin(cls, client: Client):
        client.gamemode = cls.defaultGameMode
        cls.players.append(client)

        # login packet
        playData: bytes = bytes()
        playData += dataTypes.writeInt(client.playerEntityId) # player entity id, EID
        playData += dataTypes.writeBoolean(False) # is hardcore
        playData += dataTypes.writeVarInt(3) # all dimention names, 3 for how many dimention names we're giving
        playData += dataTypes.writeIdentifier("minecraft:overworld")
        playData += dataTypes.writeIdentifier("minecraft:nether")
        playData += dataTypes.writeIdentifier("minecraft:the_end")
        playData += dataTypes.writeVarInt(0) # max players, used to draw tablist but now ignored
        playData += dataTypes.writeVarInt(32) # render distance (2-32)
        playData += dataTypes.writeVarInt(16) # simulation dist
        playData += dataTypes.writeBoolean(False) # reduced debug info (false for development)
        playData += dataTypes.writeBoolean(ServerSettings.gameRules.doImmediateRespawn==False) # enable respawn screen
        playData += dataTypes.writeBoolean(ServerSettings.gameRules.doLimitedCrafting) # do limited crafting (unused by client)
        playData += dataTypes.writeVarInt( client.getRegistryData("minecraft:dimension_type", "minecraft:overworld") ) # dimention type
        playData += dataTypes.writeIdentifier("minecraft:overworld") # dimention name
        playData += dataTypes.writeSignedLong(0) # hashed seed, first 8 bytes of it TODO make it take cls.seed and hash it and shi
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
        abilitiesFlagsVal = 0
        # flagsVal |= 0x1 # if player is invulnurable
        # flagsVal |= 0x2 # if player is flying
        # flagsVal |= 0x4 # if player is allowed to fly
        # flagsVal |= 0x8 # for "create mode" (instant break blocks)
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

        # server data
        
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
        

        # update time

        # set default spawn location (optional, "home" spawn,,, not where client will spawn in)

        # game event (for telling the client to wait for chunks)
            # DO

        # set ticking state (sets the tickrate and if its frozen or not)

        # set center chunk
            # DO

        # chunk data & update light (1 for each chunk to load)
            # DO



        client.queuedOutboundPackets.extend([
            playPacket,
            changeDiffPacket, playerAbilitiesPacket, heldSlotPacket, piuPacket,
            ppcb
        ])


    @classmethod
    def run(cls):
        while True:
            if cls.isTickFrozen: continue
            cls.tick()
            time.sleep( 1 / cls.tickRate ) # 1sec per tick

    @classmethod
    def tick(cls):
        pass
