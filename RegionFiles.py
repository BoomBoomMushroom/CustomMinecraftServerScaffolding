import nbtlib
import zlib
import io
import math
from typing import Literal, TYPE_CHECKING

from dataTypes import BitSet, writePrefixedUnsignedByteArray
from dataTypes import PacketDataWriter, PacketDataReader
from ServerSettings import ServerSettings
from enumValues import *
from Registry import Registry
if TYPE_CHECKING: from client import Client # import only for type checking

class Region:
    def __init__(self, regionFilePath: str):
        # 1st sector (4KiB) is position data of chunks in the region file
        # 2nd sector is the timestamp for last update of the specific chunk
        # all other sectors are chunk payload data
        self.payload: bytes = bytes()

        self.chunkPositionOffsets: list[int] = []
        self.chunks: list[Chunk] = []
        self.chunkDataNBT: list[nbtlib.File] = []

        with open(regionFilePath, "rb") as f: self.payload = f.read()
        self.calculateChunkDataOffsets()

    def calculateChunkDataOffsets(self):
        for i in range(0, 32*32): # x and z range from 0-31 (inclusive)
            index = i * 4 # 4 bytes per entry
            offsetInSectors = (self.payload[index] << 16) | (self.payload[index+1] << 8) | (self.payload[index+2] << 0)
            lengthInSectors = self.payload[index+3] # commented out since im not gonna use it rn
            offsetBytes = offsetInSectors * (4 * 1024)
            self.chunkPositionOffsets.append(offsetBytes)
            self.chunks.append(None) # make sure to fill this up too so we can override it when we actaully read data
            self.chunkDataNBT.append(None) # make sure to fill this up too so we can override it when we actaully read data
    
    def getChunkBytesFromIndex(self, index: int) -> bytes:
        if self.chunkDataNBT[index] != None: return self.chunkDataNBT[index]

        loc = self.chunkPositionOffsets[index]
        lengthInBytes = (self.payload[loc] << 24) | (self.payload[loc+1] << 16) | (self.payload[loc+2] << 8) | (self.payload[loc+3] << 0)
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
        # mod x and z to make sure they stay within our bounds (0-31 inclusive)
        x %= 32
        z %= 32
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

class Palette:
    # biomes are represented as string identifiers
    def __init__(self, bitsPerEntry: int=0, entries: list[Block|str]=[]):
        self.bitsPerEntry: int = bitsPerEntry
        self.paletteEntries: list[Block|str] = entries
    
    def listToIndexes(self, items: list[Block|str]=[]):
        out: list[int] = []
        for item in items:
            pass
        
        pass
    
    def __contains__(self, item: Block|str):
        return item in self.paletteEntries

    @classmethod
    def bitsPerEntryCalculate(cls, entriesCount: int=0):
        bits = math.ceil(math.log2(entriesCount))
        return bits

    @classmethod
    def fromList(cls, data: list[Block|str], isBlocks: bool=True) -> Palette:
        bpe = cls.bitsPerEntryCalculate(len(data))
        if len(data) == 0: bpe = 0
        if isBlocks:
            if bpe > 8: bpe = 15 # if over the limit then make it direct
            elif bpe < 4: bpe = 4 # minimum bpe of 4
        else:
            if bpe > 3: bpe = 7 # if over the limit make it direct
        
        out = Palette(bpe, data)
        return out

class Block:
    def __init__(self, blockIdentifier: str="", blockState: dict={}):
        self.identifier = blockIdentifier
        self.properties = blockState
    
    @property
    def blockStateId(self): return Registry.getBlockStateId(self.identifier, self.properties)

    def __eq__(self, value):
        if type(value) == Block:
            return (self.identifier == self.identifier) and (self.blockStateId == value.blockStateId)
        else: raise NotImplementedError(f"Block.__eq__ not implemented against type: {type(value)}")

class SubChunk:
    def __init__(self, blocks: list[Block]=[], biomes: list[str]=[], yLevel: int=0):
        self.blocks: list[Block] = blocks # 16x16x16
        self.biomes: list[str] = biomes # a 4x4x4 (64 entries) list of biomes in the chunk section. entries are their identifiers
        
        self.yLevel: int = yLevel # the y level, not index. example values: -64, -48, -32, -16, 0, 16, 32, 48, ...,
        self.blockCount = 0 # non air blocks. if 0 the client doesn't render the chunk
        self.fluidCount = 0 # number of fluids (waterlogged blocks, and water+lava of any level)

    @classmethod
    def paletteToBlocks(cls, data: list[int], palette: Palette) -> list[Block]:
        indexes: list[int] = []
        for long in data:
            pass
        
        pass

    def getUniqueBlocks(self) -> list[Block]:
        out: list[Block] = []
        for b in self.blocks:
            if b not in out: out.append(b)
        return out

    def getPalettedContainer(self, isBiomes=False) -> tuple[int, list[int], list[int]]:
        uniqueBlocks: list[Block] = self.getUniqueBlocks()
        palette = Palette.fromList(uniqueBlocks, isBlocks=True)
        outPacked: list[int] = []
        
        
        pass
        

    def XYZToIndex(self, x: int=0, y: int=0, z: int=0):
        # clamp xyz to be between 0 and 16 (inclusive, exclusive)
        x = max(0, min(15, x))
        y = max(0, min(15, y))
        z = max(0, min(15, z))
        return x + (y * 16) + (z * 16 * 16)

    def IndexToXYZ(self, index: int=0):
        maxIndex = (16*16*16)-1
        index = max(0, min(maxIndex, index)) # clamp the index to be between 0 and 4096 (inclusive, exclusive)
        x = index % 16
        z = (index // 16) % 16
        y = index // 256
        return (x, y, z)
    
    

# TODO: make a lock/waiter on the getters like in Registry.py w/ synced registries to prevent weird stuff
class Chunk:
    def __init__(self, dataBytes):
        self.data = dataBytes
        self.nbt: nbtlib.File = None
        self.cachedPacketData: bytes = None
        
        self.isFull: bool = False
        self.generateData() # basically init but for our data

    def generateData(self):
        nbt = self.getNBT()
        if "Level" in nbt: nbt = nbt["Level"] # sometimes all of the data we want is inside of the "Level" tag.
        self.isFull = (nbt["Status"] == "minecraft:full")
        
        if self.isFull == False: return # not full, ignore it
        for sec in nbt["sections"]:
            #print(sec)
            sc = SubChunk(
                sec[""]
            )
            pass

    def getNBT(self) -> nbtlib.File:
        if self.nbt != None: return self.nbt
        nbtBytesIO = io.BytesIO()
        nbtBytesIO.write(self.data)
        nbtBytesIO.seek(0) # fml i hate this shit, i have to seek to the beginning for it to work T-T

        self.nbt = nbtlib.File.parse(nbtBytesIO)
        return self.nbt

    def getChunkPacketDummyData(self) -> bytes:
        nbt = self.getNBT()
        x = nbt["xPos"]
        z = nbt["zPos"]
        skyLightBitset = BitSet()
        blockLightBitset = BitSet()
        skyLightDatas = []
        blockLightDatas = []

        # these are for the section 1 below the world min height (1 section below our lowest section)
        skyLightBitset.append(False)
        blockLightBitset.append(False)

        packetData = PacketDataWriter()
        packetData.writeInt(x) # chunk coord x
        packetData.writeInt(z) # chunk coord z
        packetData.writeVarInt(0) # 0 heightmap

        sectionsData = PacketDataWriter()
        for sec in nbt["sections"]:
            yBottom = sec["Y"] * 16 # the start y level, add 16 to get the top y level
            solidBlockCount = 16*16*16 # default if all stone
            allBlockId = Registry.getBlockStateId("minecraft:stone", {})
            if yBottom >= 60:
                allBlockId = Registry.getBlockStateId("minecraft:air", {})
                solidBlockCount = 0

            skyLightBitset.append(True)
            skyLightDatas.append([0b1111_1111] * 2048) # 0b1111_1111 | for (16*16*16)/2 so 4 bits per block
            blockLightBitset.append(True)
            blockLightDatas.append([0b1111_1111] * 2048)

            sectionsData.writeShort(solidBlockCount) # solid block count
            sectionsData.writeShort(0) # fluid count, 0
            # block data paletted
            sectionsData.writeUnsignedByte(0) # bits per entry
            sectionsData.writeVarInt(allBlockId) # block id
            # biome data paletted
            sectionsData.writeUnsignedByte(0) # bits per entry
            sectionsData.writeVarInt(0) # whatever biome is id 0
            #print(sec, sec.keys())
            pass
        packetData.writeVarInt(len(sectionsData))
        packetData.writeRawBytes(sectionsData)

        # these are for the section 1 above the world max height (1 section above our highest section)
        skyLightBitset.append(False)
        blockLightBitset.append(False)

        skyLightDatasRaw = [ writePrefixedUnsignedByteArray(arr) for arr in skyLightDatas ]
        blockLightDatasRaw = [ writePrefixedUnsignedByteArray(arr) for arr in blockLightDatas ]

        packetData.writeVarInt(0) # 0 block entities
        # light data vv
        packetData.writeBitSet(skyLightBitset) # sky light bitset
        packetData.writeBitSet(blockLightBitset) # block light bitset
        packetData.writeBitSet(BitSet()) # bitset of empty sky light
        packetData.writeBitSet(BitSet()) # bitset of empty block light
        packetData.writePrefixedRawDataArray(skyLightDatasRaw) # sky light data arr
        packetData.writePrefixedRawDataArray(blockLightDatasRaw) # block light data arr
        return packetData

    def getChunkPacketData(self) -> bytes:
        if self.cachedPacketData != None:
            #print("I'm cached :D sending that back")
            return self.cachedPacketData

        nbt = self.getNBT()
        if "Level" in nbt: nbt = nbt["Level"] # sometimes all of the data we want is inside of the "Level" tag.
        chunkStatus = nbt["Status"]
        if chunkStatus != "minecraft:full":
            # chunk is still generating in some way, it is not done,,, ignore it
            return bytes()

        x = nbt["xPos"]
        z = nbt["zPos"]

        chunkHeightmaps: list[tuple[str, list[int]]] = []
        for key in nbt["Heightmaps"]:
            # these keys below are the only ones the wiki displays w/ it's id so the only ones im sending
            if key not in ["WORLD_SURFACE", "MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES"]: continue
            hmap = nbt["Heightmaps"][key]
            chunkHeightmaps.append((key, hmap))

        skyLightBitset = BitSet()
        blockLightBitset = BitSet()
        skyLightDatas = []
        blockLightDatas = []

        # these are for the section 1 below the world min height (1 section below our lowest section)
        skyLightBitset.append(False)
        blockLightBitset.append(False)

        packetData = PacketDataWriter()
        packetData.writeInt(x) # chunk coord x
        packetData.writeInt(z) # chunk coord z

        packetData.writeVarInt(len(chunkHeightmaps)) # length of heightmap array
        for hmap in chunkHeightmaps:
            packetData.writeVarInt( HEIGHTMAP_TYPE_Enum[hmap[0]] ) # type of heightmap
            packetData.writeVarInt(len(hmap[1])) # length of long array
            for long in hmap[1]: packetData.writeLong(long) # the longs IN the array

        sectionsData = PacketDataWriter()
        for sec in nbt["sections"]:
            solidBlockCount = 16*16*16 # all blocks in the section are "filled"; so the chunk still rendered w/o counting up everything
            fluidBlockCount = 16*16*16

            def getPaletteEntryId(entry: dict|str, isBiome: bool=False) -> int:
                id = 0
                if isBiome:
                    id = Registry.getSyncedRegistry("minecraft:worldgen/biome").getEntryIndex(entry)
                else:
                    # block state palette
                    identifier = entry["Name"]
                    properties = entry.get("Properties", {})
                    id = Registry.getBlockStateId(identifier, properties)

                return id

            def writePalettedContainer( refName: str, isBiome: bool=False, minBits: int=4, maxBits: int=8):
                containerBytes = PacketDataWriter()
                palette = sec[refName]["palette"]
                bitsMin = (len(palette) - 1).bit_length()
                bitsPerEntry = max(bitsMin, minBits)

                # if 1 then it is all one block/biome and we just say that
                if len(palette) == 1:
                    containerBytes.writeUnsignedByte(0) # bits per entry, 0=single valued
                    paletteId = getPaletteEntryId(palette[0], isBiome)
                    containerBytes.writeVarInt(paletteId)
                else:
                    # Copy and paste the palette and the blocks list into the packet
                    containerBytes.writeUnsignedByte(bitsPerEntry) # bits per entry
                    containerBytes.writeVarInt(len(palette)) # length of the entries array
                    for paletteEntry in palette:
                        entryId = getPaletteEntryId(paletteEntry, isBiome)
                        containerBytes.writeVarInt(entryId)

                    longData = sec[refName]["data"]
                    for long in longData: containerBytes.writeLong(long)

                return containerBytes

            # TODO Send the real light data
            skyLightBitset.append(True)
            skyLightDatas.append([0b1111_1111] * 2048) # 0b1111_1111 | for (16*16*16)/2 so 4 bits per block
            blockLightBitset.append(True)
            blockLightDatas.append([0b1111_1111] * 2048)

            sectionsData.writeShort(solidBlockCount) # solid block count
            sectionsData.writeShort(fluidBlockCount) # fluid count
            # block data paletted
            sectionsData.writeRawBytes(writePalettedContainer("block_states"))
            # biome data paletted
            sectionsData.writeRawBytes(writePalettedContainer("biomes", isBiome=True, minBits=1))
            
        packetData.writeVarInt(len(sectionsData))
        packetData.writeRawBytes(sectionsData)

        # these are for the section 1 above the world max height (1 section above our highest section)
        skyLightBitset.append(False)
        blockLightBitset.append(False)

        skyLightDatasRaw = [ writePrefixedUnsignedByteArray(arr) for arr in skyLightDatas ]
        blockLightDatasRaw = [ writePrefixedUnsignedByteArray(arr) for arr in blockLightDatas ]

        packetData.writeVarInt(0) # 0 block entities
        # light data vv
        packetData.writeBitSet(skyLightBitset) # sky light bitset
        packetData.writeBitSet(blockLightBitset) # block light bitset
        packetData.writeBitSet(BitSet()) # bitset of empty sky light
        packetData.writeBitSet(BitSet()) # bitset of empty block light
        packetData.writePrefixedRawDataArray(skyLightDatasRaw) # sky light data arr
        packetData.writePrefixedRawDataArray(blockLightDatasRaw) # block light data arr

        self.cachedPacketData = packetData
        return packetData


# TODO: when chunks are loaded we should decode them into a bunch of blocks so it's easy to modify it
#   after each change we can cache the packet data we would need

if __name__ == "__main__":
    # -341, 57, -341
    r = Region("./world/overworld/r.-1.-1.mca")
    c = r.getChunk(11, 11)
    #print(c.getNBT().keys())
    #c.getChunkPacketDummyData()

