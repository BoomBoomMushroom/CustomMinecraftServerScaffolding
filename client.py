import packets
import dataTypes
from ServerSettings import ServerSettings

import os
import json
import io
import nbtlib

class Client:
    def __init__(self):
        self.username = ""
        self.UUID = ""

        self.registries = []

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
        """
        queuedRegisters = [
            "banner_pattern", "damage_type", "dimension_type", "instrument", "jukebox_song", "painting_variant",
            "sulfur_cube_archetype", "trim_material", "worldgen/biome", "cat_variant", "cat_sound_variant",
            "chicken_variant", "chicken_sound_variant", "cow_variant", "cow_sound_variant", "frog_variant",
            "pig_variant", "pig_sound_variant", "wolf_variant", "wolf_sound_variant", "zombie_nautilus_variant",
        ]
        """
        #"""
        queuedRegisters = [
            "banner_pattern", "chat_type", "damage_type", "dialog", "dimension_type", "enchantment", "instrument",
            "jukebox_song", "painting_variant", "sulfur_cube_archetype", "test_environment", "test_instance",
            "timeline", "trim_material", "trim_pattern", "world_clock", "worldgen/biome", "cat_variant",
            "cat_sound_variant", "chicken_variant", "chicken_sound_variant", "cow_variant", "cow_sound_variant",
            "frog_variant", "pig_variant", "pig_sound_variant", "wolf_variant", "wolf_sound_variant",
            "zombie_nautilus_variant",
        ]
        #"""
        #queuedRegisters = ["timeline", "dimension_type", "world_clock"]
        #queuedRegisters = os.listdir(ServerSettings.registriesPath)
        #queuedRegisters.remove("tags") # this is the registry tags folder, we do not want to register these
        #queuedRegisters.remove("recipe")

        for register in queuedRegisters:
            path = f"{ServerSettings.registriesPath}/{register}"
            tagFiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            tagFiles = [f for f in tagFiles if f.endswith(".json")]

            packetData = bytes()
            packetData += dataTypes.writeIdentifier(f"minecraft:{register}")
            packetData += dataTypes.writeVarInt(len(tagFiles))

            for file in tagFiles:
                fileData = "{}"
                with open(f"{path}/{file}") as f: fileData = f.read()

                nbtBytesIO = io.BytesIO()
                #print(path, file, fileData)
                nbt = nbtlib.parse_nbt(fileData)
                nbtlib.File(nbt).write(nbtBytesIO)
                nbtBytes: bytes = nbtBytesIO.getvalue()
                if ServerSettings.protocol >= 764:
                    # remove bytes at indexes 1 and 2 since after 1.20.2 compound tags dont send their name when using networks for SOME reason
                    nbtBytes = bytes([nbtBytes[0]]) + nbtBytes[3:]
                
                nameNoExtention = ".".join( file.split(".")[:-1] )
                packetData += dataTypes.writeIdentifier(f"minecraft:{nameNoExtention}")
                packetData += dataTypes.writeBoolean(True)
                packetData += nbtBytes

                self.registries.append(f"minecraft:{nameNoExtention}") # make sure we don't lose track of it!

            registryPacket = packets.RegistryData_ClientBound(packetData)
            self.queuedOutboundPackets.append( registryPacket )

        #queuedTagsRegistries = ["timeline", "block"]
        queuedTagsRegistries = os.listdir(ServerSettings.registryTagsPath)
        """
        queuedTagsRegistries.remove("potion")
        queuedTagsRegistries.remove("fluid")
        queuedTagsRegistries.remove("game_event")
        queuedTagsRegistries.remove("entity_type")
        queuedTagsRegistries.remove("point_of_interest_type")
        queuedTagsRegistries.remove("item")
        queuedTagsRegistries.remove("block")
        """
        
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
                    print(tagIdentifier, value)
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
                        #print(self.registries, value, path, tagFile)
                        idx = -1
                        try:
                            idx = self.registries.index(value)
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
            print(len(tagObjects))
            entryBytes: bytes = bytes()
            entryBytes += dataTypes.writeIdentifier(f"minecraft:{tagRegister}")
            entryBytes += dataTypes.writeVarInt(len(tagObjects))
            for tagObj in tagObjects:
                entryBytes += tagObj
            taggedRegistersEntries.append(entryBytes)
            print("taggedregentry added")


        updateTagsPacketData = bytes()
        updateTagsPacketData += dataTypes.writeVarInt(len(taggedRegistersEntries))
        for taggedReg in taggedRegistersEntries:
            updateTagsPacketData += taggedReg
        updateTagsPacket = packets.UpdateTags_ClientBound(updateTagsPacketData)
        self.queuedOutboundPackets.append(updateTagsPacket)


        finishConfigPacket = packets.FinishConfiguration_ClientBound()
        self.queuedOutboundPackets.append(finishConfigPacket)

