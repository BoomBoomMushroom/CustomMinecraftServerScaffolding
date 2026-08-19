import packets
import dataTypes
from ServerSettings import ServerSettings

import os
import json
import io
import nbtlib
import random

class Client:
    def __init__(self):
        self.username = ""
        self.UUID = ""
        self.posX: float = 0
        self.posY: float = 0
        self.posZ: float = 0
        self.velX: float = 0
        self.velY: float = 0
        self.velZ: float = 0
        self.yaw: float = 0
        self.pitch: float = 0
        self.onGround = False

        # Special numbers that can tick up, keep track of these
        self.playerEntityId: int = dataTypes.readInt(random.randbytes(4))[0] # ramdom 4 byte EID
        self.teleportId: int = random.randint(1, 999)

        self.registries: dict[str, list[int]] = {}

        self.state: packets.ConnectionState = "HANDSHAKING"
        self.socketData: bytes = bytes()
        self.unhandledPackets: list[packets.Packet] = []
        self.queuedOutboundPackets: list[packets.Packet] = []

    def readAllPackets(self):
        while True:
            # typing is given by the return typing of decodePacket (a tuple[bytes, Packet])
            self.socketData, packet = packets.decodePacket(self.socketData, self.state)
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
        if packetResponse.updatePosition != None: self.posX, self.posY, self.posZ = packetResponse.updatePosition
        if packetResponse.updateRoation != None: self.yaw, self.pitch = packetResponse.updateRoation
        if packetResponse.updateOnGround != None: self.onGround = packetResponse.updateOnGround
        if packetResponse.updateAgainstWall != None: pass # dont care abt it rn

        # client todo stuff
        if packetResponse.generateAndSendRegistryData == True: self.generateAndSendRegistryData()
        if packetResponse.giveLoginPacket == True: self.generateAndSendLoginPacket()
        if packetResponse.stuffAfterLoginPacket == True: self.generateAndSendStuffAfterLoginPacket()

        # info from packets to know stuff happened
        if packetResponse.teleportId != None:
            if packetResponse.teleportId == self.teleportId:
                print(f"~~~ Teleport (id: {packetResponse.teleportId}) was successful")

        

    def handlePackets(self):
        self.readAllPackets()

        while len(self.unhandledPackets) > 0:
            packet = self.unhandledPackets.pop(0) # pop the first one for a FIFO queue
            print(packet)
            try:
                response = packet.handle()
                self.handlePacketReturn(response)
            except Exception as e:
                #raise e
                self.queuedOutboundPackets = None # the thread will see this is None and end the connection
                pass

    def readInBytes(self, newData: bytes):
        self.socketData += newData
        self.handlePackets()

    def generateAndSendRegistryData(self):
        #queuedRegisters = os.listdir(ServerSettings.registriesPath)
        queuedRegisters: list[str] = [x[0].split(ServerSettings.registriesPath)[1][1:] for x in os.walk(ServerSettings.registriesPath)]
        queuedRegisters.remove("")
        queuedRegisters = [_ for _ in queuedRegisters if _.startswith("tags")==False] # remove tags folders
        #queuedRegisters.remove("tags") # this is the registry tags folder, we do not want to register these
        
        # remove these once since we cant parse them as NBT
        queuedRegisters.remove("recipe")
        queuedRegisters = [_ for _ in queuedRegisters if _.startswith("villager_trade")==False]
        queuedRegisters = [_ for _ in queuedRegisters if _.startswith("datapacks")==False]
        queuedRegisters.remove("worldgen/density_function")

        for register in queuedRegisters:
            path = f"{ServerSettings.registriesPath}/{register}"
            """
            tagFiles = []
            for (dirpath, dirname, filenames) in os.walk(path):
                dirpath = dirpath.split(path)[1]
                if dirpath != "":
                    fs = [dirpath[1:]+"/"+_ for _ in filenames]
                else:
                    fs = filenames
                tagFiles.extend(fs)
            """

            tagFiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            tagFiles: list[str] = [f for f in tagFiles if f.endswith(".json")]

            """
            if register == "worldgen":
                # remove the following:
                tagFiles = [f for f in tagFiles if f.startswith("density_function/")==False]
            """
                

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

    def generateAndSendLoginPacket(self):
        playData: bytes = bytes()
        playData += dataTypes.writeInt(self.playerEntityId) # player entity id, EID
        playData += dataTypes.writeBoolean(False) # is hardcore
        # dimention names
        playData += dataTypes.writeVarInt(3)
        playData += dataTypes.writeIdentifier("minecraft:overworld")
        playData += dataTypes.writeIdentifier("minecraft:nether")
        playData += dataTypes.writeIdentifier("minecraft:the_end")
        playData += dataTypes.writeVarInt(0) # max players, used to draw tablist but now ignored
        playData += dataTypes.writeVarInt(32) # render distance (2-32)
        playData += dataTypes.writeVarInt(16) # simulation dist
        playData += dataTypes.writeBoolean(False) # reduced debug info (false for development)
        playData += dataTypes.writeBoolean(ServerSettings.gameRules.doImmediateRespawn==False) # enable respawn screen
        playData += dataTypes.writeBoolean(False) # do limited crafting (unused by client)
        playData += dataTypes.writeVarInt( self.registries.get("minecraft:dimension_type").index("minecraft:overworld") ) # dimention type
        playData += dataTypes.writeIdentifier("minecraft:overworld") # dimention name
        playData += dataTypes.writeSignedLong(0) # hashed seed, first 8 bytes of it
        playData += dataTypes.writeUnsignedByte(2) # game mode, 0=surv, 1=crea, 2=adv, 3=spec
        playData += dataTypes.writeByte(-1) # previous gamemode, used for F3+F4. Same as above just -1 is null
        playData += dataTypes.writeBoolean(False) # is debug world
        playData += dataTypes.writeBoolean(False) # is superflat world
        playData += dataTypes.writeBoolean(False) # has death location. makes the next 2 fields present
        #playData += dataTypes.writeIdentifier("minecraft:overworld") # last death dimention name
        #playData += dataTypes.writePosition(fill it out here) # last death pos
        playData += dataTypes.writeVarInt(0) # portal cooldown in ticks
        playData += dataTypes.writeVarInt(60) # sea level
        playData += dataTypes.writeBoolean(False) # online mode
        playData += dataTypes.writeBoolean(False) # enforces secure chat

        playPacket = packets.Login_ClientBound(playData)
        self.queuedOutboundPackets.append(playPacket)

        response = packets.HandleResponse()
        response.stuffAfterLoginPacket = True
        self.handlePacketReturn(response)

    def generateAndSendStuffAfterLoginPacket(self):
        # change difficulty packet
        
        # player abilities packet
        
        # set held item packet
        
        # update recipes packet
        
        # entity event packet | for the OP permission level
        
        # commands packet
        
        # update recipe book packet
        
        # syncronize player position packet
        ppcbData: bytes = bytes()
        self.teleportId += 1
        ppcbData += dataTypes.writeVarInt(self.teleportId) # teleport id, will be used to confirm in confirm teleport packet
        ppcbData += dataTypes.writeDouble(self.posX) # X
        ppcbData += dataTypes.writeDouble(self.posY) # Y
        ppcbData += dataTypes.writeDouble(self.posZ) # Z
        ppcbData += dataTypes.writeDouble(self.velX) # Vx
        ppcbData += dataTypes.writeDouble(self.velY) # Vy
        ppcbData += dataTypes.writeDouble(self.velZ) # Vz
        ppcbData += dataTypes.writeFloat(self.yaw) # yaw, in degrees
        ppcbData += dataTypes.writeFloat(self.pitch) # pitch, in degrees
        ppcbData += dataTypes.writeInt(0) # teleport flags (https://minecraft.wiki/w/Java_Edition_protocol/Packets#Teleport_Flags)
        ppcb = packets.PlayerPosition_ClientBound(ppcbData)

        # server data
        
        # player info update

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



        self.queuedOutboundPackets.extend([ ppcb ])

