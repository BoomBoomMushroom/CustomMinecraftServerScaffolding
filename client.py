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
        queuedRegisters = ["dimension_type", "timeline"]

        for register in queuedRegisters:
            path = f"./registries/26.2/minecraft/{register}"
            files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

            packetData = bytes()
            packetData += dataTypes.writeIdentifier(f"minecraft:{register}")
            packetData += dataTypes.writeVarInt(len(files))

            for file in files:
                fileData = "{}"
                with open(f"{path}/{file}") as f: fileData = f.read()

                nbtBytesIO = io.BytesIO()
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

        queuedTags = ["timeline"]
        print(self.registries)
        raise Exception("")

        updateTagsPacketData = bytes()
        updateTagsPacket = packets.UpdateTags_ClientBound(updateTagsPacketData)

        self.queuedOutboundPackets.append(updateTagsPacket)


        finishConfigPacket = packets.FinishConfiguration_ClientBound()
        self.queuedOutboundPackets.append(finishConfigPacket)

