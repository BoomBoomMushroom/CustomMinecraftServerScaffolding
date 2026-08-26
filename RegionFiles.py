import dataTypes
from ServerSettings import ServerSettings

import nbtlib
import zlib
import io

class Region:
    def __init__(self, regionFilePath: str):
        # 1st sector (4KiB) is position data of chunks in the region file
        # 2nd sector is the timestamp for last update of the specific chunk
        # all other sectors are chunk payload data
        self.payload: bytes = bytes()

        self.chunkPositionOffsets: list[int] = []
        self.chunks: list[int] = []
        self.chunkDataNBT: list[nbtlib.File] = []

        with open(regionFilePath, "rb") as f: self.payload = f.read()
        self.calculateChunkDataOffsets()

    def calculateChunkDataOffsets(self):
        for idx in range(0, 32*32): # x and z range from 0-31 (inclusive)
            offsetInSectors = (self.payload[idx] << 16) + (self.payload[idx+1] << 8) + (self.payload[idx+2] << 0)
            # lengthInSectors = self.payload[idx+3] # commented out since im not gonna use it rn
            offsetBytes = offsetInSectors * 4096
            self.chunkPositionOffsets.append(offsetBytes)
            self.chunks.append(None) # make sure to fill this up too so we can override it when we actaully read data
            self.chunkDataNBT.append(None) # make sure to fill this up too so we can override it when we actaully read data
    
    def getChunkBytesFromIndex(self, index: int) -> bytes:
        if self.chunkDataNBT[index] != None: return self.chunkDataNBT[index]

        loc = self.chunkPositionOffsets[index]
        lengthInBytes = (self.payload[loc] << 24) + (self.payload[loc+1] << 16) + (self.payload[loc+2] << 8) + (self.payload[loc+3] << 0)
        compressionType = self.payload[loc+4]
        chunkDataCompressed: bytes = self.payload[loc+5:loc+5+lengthInBytes-1] # compression type is counted in the length
        chunkData: bytes = bytes()

        if compressionType == 2: # this is realistically the only compression type that will be shown
            chunkData = zlib.decompress(chunkDataCompressed)
        else:
            raise NotImplementedError(f"{compressionType=} not implemented!")

        self.chunkDataNBT[index] = chunkData # write this data down so we don't forget!
        return chunkData

    def getChunk(self, x: int, z: int) -> Chunk:
        idx = x + 32*z
        if self.chunks[idx] != None: return self.chunks[idx]
        dataBytes = self.getChunkBytesFromIndex(idx)
        c = Chunk(dataBytes)
        self.chunks[idx] = c
        return c

    def getChunkNBT(self, x: int, z: int) -> nbtlib.File:
        c: Chunk = self.getChunk(x, z)
        return c.getNBT()

    # TODO: have the ability to modify the chunks and maybe save the region file back again

class Chunk:
    def __init__(self, dataBytes):
        self.data = dataBytes
        self.nbt: nbtlib.File = None

    def getNBT(self) -> nbtlib.File:
        if self.nbt != None: return self.nbt
        nbtBytesIO = io.BytesIO()
        nbtBytesIO.write(self.data)
        nbtBytesIO.seek(0) # fml i hate this shit, i have to seek to the beginning for it to work T-T

        self.nbt = nbtlib.File.parse(nbtBytesIO)
        return self.nbt

    def getChunkPacketData(self) -> bytes:
        nbt = self.getNBT()
        x = nbt["xPos"]
        z = nbt["zPos"]

        packetData = bytes()
        packetData += dataTypes.writeInt(x) # chunk coord x
        packetData += dataTypes.writeInt(z) # chunk coord z
        packetData += dataTypes.writeVarInt(0) # 0 heightmap

        sectionsData = bytes()
        for sec in nbt["sections"]:
            yBottom = sec["Y"] * 16 # the start y level, add 16 to get the top y level
            solidBlockCt = 16*16*16 # default if all stone
            allBlockId = ServerSettings.getRegistryData("minecraft:block", "minecraft:stone")
            if yBottom >= 60:
                allBlockId = ServerSettings.getRegistryData("minecraft:block", "minecraft:air")
                solidBlockCt = 0

            sectionsData += dataTypes.writeShort(solidBlockCt) # solid block count
            sectionsData += dataTypes.writeShort(0) # fluid count, 0    
            # block data paletted
            sectionsData += dataTypes.writeUnsignedByte(0) # bits per entry
            sectionsData += dataTypes.writeVarInt(allBlockId) # block id
            # biome data paletted
            sectionsData += dataTypes.writeUnsignedByte(0) # bits per entry
            sectionsData += dataTypes.writeVarInt(0) # whatever biome is id 0
            #print(sec, sec.keys())
            pass
        packetData += dataTypes.writeVarInt(len(sectionsData))
        packetData += sectionsData

        packetData += dataTypes.writeVarInt(0) # 0 block entities
        # light data vv
        packetData += dataTypes.writeVarInt(0) # bitset size of 0
        packetData += dataTypes.writeVarInt(0) # bitset size of 0
        packetData += dataTypes.writeVarInt(0) # bitset size of 0
        packetData += dataTypes.writeVarInt(0) # bitset size of 0
        packetData += dataTypes.writeVarInt(0) # 0 light arr
        packetData += dataTypes.writeVarInt(0) # 0 light arr
        return packetData

"""
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
            dataTypes.writeVarInt( HEIGHTMAP_TYPE_Enum[hmap[0]] ) # type of heightmap
            dataTypes.writeVarInt(len(hmap[1])) # length of long array
            for long in hmap[1]: dataTypes.writeLong(long) # the longs IN the array
            
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
"""


if __name__ == "__main__":
    r = Region("./world/overworld/r.0.0.mca")
    c = r.getChunk(0, 0)
    print(c.getNBT().keys())
    c.getChunkPacketData()

