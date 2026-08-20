import packets
import dataTypes
from ServerSettings import ServerSettings
from world import World
from enumValues import *

import os
import json
import io
import nbtlib
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


class Client:
    def __init__(self):
        self.username = ""
        self.UUID = None
        self.posX: float = 0
        self.posY: float = 70
        self.posZ: float = 0
        self.velX: float = 0
        self.velY: float = 0
        self.velZ: float = 0
        self.yaw: float = 0
        self.pitch: float = 0
        self.onGround = False
        self.gamemode: GAMEMODE = "NULL"

        self.isUnsignedplayerPropertiesFromAPI: bool = False
        self.playerPropertiesFromAPI: list[dict[str, str]] = [] # list of properties from the mojang api for our player. eg textures & capes

        # Special numbers that can tick up, keep track of these
        self.playerEntityId: int = dataTypes.readInt(random.randbytes(4))[0] # ramdom 4 byte EID
        self.teleportId: int = random.randint(1, 999)

        self.registries: dict[str, list[int]] = {}

        self.state: packets.ConnectionState = "HANDSHAKING"
        self.socketData: bytes = bytes()
        self.unhandledPackets: list[packets.Packet] = []
        self.queuedOutboundPackets: list[packets.Packet] = []

    def getRegistryData(self, namespace: str, identifier: str) -> int:
        return self.registries.get(namespace).index(identifier)

    def handlePacketReturn(self, packetResponse: packets.HandleResponse):
        if packetResponse == None: return

        # connection updates
        self.queuedOutboundPackets.extend( packetResponse.respondWithPackets )
        if packetResponse.nextConnectionState != None: self.state = packetResponse.nextConnectionState

        # update the client's data
        if packetResponse.updateUsername != None: self.username = packetResponse.updateUsername
        if packetResponse.updateUUID != None:
            self.UUID = packetResponse.updateUUID
            self.generatePlayerPropertiesFromAPI() # now that we have the UUID fetch it's data from mojang servers
            
        if packetResponse.updatePosition != None: self.posX, self.posY, self.posZ = packetResponse.updatePosition
        if packetResponse.updateRoation != None: self.yaw, self.pitch = packetResponse.updateRoation
        if packetResponse.updateOnGround != None: self.onGround = packetResponse.updateOnGround
        if packetResponse.updateAgainstWall != None: pass # dont care abt it rn

        # client todo stuff
        if packetResponse.sendLoginFinishedPacket == True: self.sendLoginFinishedPacket()
        if packetResponse.generateAndSendRegistryData == True: self.generateAndSendRegistryData()
        if packetResponse.clientLoginToWorld == True: World.onPlayerJoin(self)

        # info from packets to know stuff happened
        if packetResponse.teleportId != None:
            if packetResponse.teleportId == self.teleportId:
                print(f"~~~ Teleport (id: {packetResponse.teleportId}) was successful")

    def generatePlayerPropertiesFromAPI(self):
        if self.UUID == None: return

        uuidString = "".join([ hex(b).split("0x")[1].zfill(2) for b in self.UUID ])
        r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuidString}?unsigned={self.isUnsignedplayerPropertiesFromAPI}")
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
                #self.queuedOutboundPackets = None # the thread will see this is None and end the connection
                pass

    def readInBytes(self, newData: bytes):
        self.socketData += newData
        self.handlePackets()

    def getGameProfile(self, ignoreUUID=False) -> bytes:
        out = bytes()
        if ignoreUUID == False: out += self.UUID
        out += dataTypes.writeString(self.username)
        out += dataTypes.writeVarInt( len(self.playerPropertiesFromAPI) )
        for property in self.playerPropertiesFromAPI:
            isSigned = not self.isUnsignedplayerPropertiesFromAPI
            out += dataTypes.writeString(property["name"])
            out += dataTypes.writeString(property["value"])
            out += dataTypes.writeBoolean( isSigned )
            if isSigned: out += dataTypes.writeString(property["signature"])
        return out

    def sendLoginFinishedPacket(self):
        packetData: bytes = bytes()
        packetData += self.getGameProfile()        
        packetData += bytes(16) # Session ID (as a UUID) | I don't think it really matters so im making it all 0s for right now

        self.queuedOutboundPackets.append(packets.LoginFinished_ClientBound(packetData))

    def generateAndSendRegistryData(self):
        """
        queuedRegisters: list[str] = getAllSubDirs(ServerSettings.registriesPath)
        filteredQueuedRegisters = []
        for reg in queuedRegisters:
            if reg.startswith("tags"): continue # this is the registry tags folder, we do not want to register these

            # remove these once since we cant parse them as NBT or they're so big i just wanna skip them
            if reg.startswith("recipe"): continue
            if reg.startswith("villager_trade"): continue
            if reg.startswith("datapacks"): continue
            if reg.startswith("advancement"): continue
            if reg.startswith("loot_table"): continue
            if reg.startswith("structure"): continue
            if reg.startswith("trial_spawner"): continue
            if reg.startswith("trade_set"): continue
            if reg.startswith("worldgen/template_pool"): continue
            if reg.startswith("worldgen/density_function"): continue

            filteredQueuedRegisters.append(reg)
        queuedRegisters = filteredQueuedRegisters
        """

        # from the above list, when printed i just copied it here to speed it up for now
        queuedRegisters = ["enchantment", "jukebox_song", "test_instance", "wolf_variant", "test_environment", "chicken_sound_variant", "cow_sound_variant", "pig_sound_variant", "dimension_type", "enchantment_provider", "enchantment_provider/raid", "sulfur_cube_archetype", "cat_variant", "cow_variant", "chat_type", "frog_variant", "damage_type", "worldgen", "worldgen/structure", "worldgen/world_preset", "worldgen/biome", "worldgen/placed_feature", "worldgen/structure_set", "worldgen/noise_settings", "worldgen/processor_list", "worldgen/configured_feature", "worldgen/multi_noise_biome_source_parameter_list", "worldgen/flat_level_generator_preset", "worldgen/noise", "worldgen/noise/nether", "worldgen/configured_carver", "banner_pattern", "zombie_nautilus_variant", "world_clock", "painting_variant", "cat_sound_variant", "wolf_sound_variant", "timeline", "dialog", "chicken_variant", "pig_variant", "trim_pattern", "instrument", "trim_material"]
        
        for register in queuedRegisters:
            print(register)
            path = f"{ServerSettings.registriesPath}/{register}"

            tagFiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            tagFiles: list[str] = [f for f in tagFiles if f.endswith(".json")]
            
            packetData = bytes()
            packetData += dataTypes.writeIdentifier(f"minecraft:{register}")
            packetData += dataTypes.writeVarInt(len(tagFiles))

            for file in tagFiles:
                fileData = "{}"
                with open(f"{path}/{file}") as f: fileData = f.read()

                nbtBytesIO = io.BytesIO()
                try:
                    nbt = nbtlib.parse_nbt(fileData)
                except Exception as e:
                    print(path, file, fileData)
                    raise e
                nbtlib.File(nbt).write(nbtBytesIO)
                nbtBytes: bytes = nbtBytesIO.getvalue()
                if ServerSettings.protocol >= 764:
                    # remove bytes at indexes 1 and 2 since after 1.20.2 compound tags dont send their name when using networks for SOME reason
                    nbtBytes = bytes([nbtBytes[0]]) + nbtBytes[3:]
                
                nameNoExtention = ".".join( file.split(".")[:-1] )
                packetData += dataTypes.writeIdentifier(f"minecraft:{nameNoExtention}")
                packetData += dataTypes.writeBoolean(True)
                packetData += nbtBytes

                key = f"minecraft:{register}"
                arr = self.registries.get(key, [])
                arr.append(f"minecraft:{nameNoExtention}") # make sure we don't lose track of it!
                self.registries[key] = arr

                #print(register, file)

            if packetData == None: continue
            registryPacket = packets.RegistryData_ClientBound(packetData)
            self.queuedOutboundPackets.append( registryPacket )


        # registry tags
        queuedTagsRegistries = os.listdir(ServerSettings.registryTagsPath)
        queuedTagsRegistries.remove("villager_trade")
        queuedTagsRegistries.remove("worldgen")

        
        tagIdentifiersToValues: dict[str, list[int]] = {}

        taggedRegistersEntries: list[bytes] = []
        while len(queuedTagsRegistries) > 0:
            skipTagRegister = False
            tagRegister = queuedTagsRegistries.pop(0)
            path = f"{ServerSettings.registryTagsPath}/{tagRegister}"
            tagFiles = []
            for (dirpath, dirname, filenames) in os.walk(path):
                dirpath = dirpath.split(path)[1]
                if dirpath != "":
                    fs = [dirpath[1:]+"/"+_ for _ in filenames]
                else:
                    fs = filenames
                tagFiles.extend(fs)
            #tagFiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            tagObjects: list[bytes] = []

            while len(tagFiles) > 0:
                tagFile = tagFiles.pop(0)
                tagName = tagFile.split(".")[0]
                tagIdentifier = "minecraft:" + tagName
                tagValuesStr: list[str] = []
                with open(f"{path}/{tagFile}") as f: tagValuesStr = json.load(f)["values"]

                skipTag = False
                totalTagIndexes: list[int] = []
                for value in tagValuesStr:
                    valueIndexes: list[int] = []
                    if value[0] == "#":
                        # This is a reference to another tag
                        value = value[1:]
                        if value in tagIdentifiersToValues:
                            # We already computed this tag, yay!
                            valueIndexes.extend( tagIdentifiersToValues[value] )
                        else:
                            # We haven't computed this yet D:
                            skipTag = True
                            break
                    else:
                        idx = -1
                        try:
                            arr = self.registries.get(f"minecraft:{tagRegister}", [])
                            idx = arr.index(value)
                        except ValueError as e:
                            try:
                                idx = ServerSettings.staticRegistries[f"minecraft:{tagRegister}"]["entries"][value]["protocol_id"]
                            except:
                                # probably didnt get to it yet, will do later
                                queuedTagsRegistries.append(tagRegister)
                                skipTagRegister = True
                                break
                        except Exception as e: raise e

                        valueIndexes.append( idx )

                    tagIdentifiersToValues[ tagIdentifier ] = valueIndexes
                    totalTagIndexes.extend(valueIndexes)

                if skipTagRegister == True:
                    break

                if skipTag == True:
                    tagFiles.append(tagFile)
                    continue

                # If we're here our tag is done has been processed
                tagObject: bytes = bytes()
                tagObject += dataTypes.writeIdentifier(tagIdentifier)
                tagObject += dataTypes.writeVarInt(len(totalTagIndexes))
                for idx in totalTagIndexes:
                    tagObject += dataTypes.writeVarInt(idx)

                tagObjects.append(tagObject)

            if skipTagRegister: continue

            # All tags processed have been processed
            entryBytes: bytes = bytes()
            entryBytes += dataTypes.writeIdentifier(f"minecraft:{tagRegister}")
            entryBytes += dataTypes.writeVarInt(len(tagObjects))
            for tagObj in tagObjects:
                entryBytes += tagObj
            taggedRegistersEntries.append(entryBytes)


        updateTagsPacketData = bytes()
        updateTagsPacketData += dataTypes.writeVarInt(len(taggedRegistersEntries))
        for taggedReg in taggedRegistersEntries:
            updateTagsPacketData += taggedReg
        updateTagsPacket = packets.UpdateTags_ClientBound(updateTagsPacketData)
        self.queuedOutboundPackets.append(updateTagsPacket)


        finishConfigPacket = packets.FinishConfiguration_ClientBound()
        self.queuedOutboundPackets.append(finishConfigPacket)

