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
        self.chunkDataNBT: list[nbtlib.File] = []

        with open(regionFilePath, "rb") as f: self.payload = f.read()
        self.calculateChunkDataOffsets()

    def calculateChunkDataOffsets(self):
        for idx in range(0, 32*32): # x and z range from 0-31 (inclusive)
            offsetInSectors = (self.payload[idx] << 16) + (self.payload[idx+1] << 8) + (self.payload[idx+2] << 0)
            # lengthInSectors = self.payload[idx+3] # commented out since im not gonna use it rn
            offsetBytes = offsetInSectors * 4096
            self.chunkPositionOffsets.append(offsetBytes)
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

    def getChunkBytes(self, x: int, z: int) -> bytes:
        idx = x + 32*z
        return self.getChunkBytesFromIndex(idx)

    def getChunkNBT(self, x: int, z: int) -> nbtlib.File:
        data: bytes = self.getChunkBytes(x, z)
        nbtBytesIO = io.BytesIO()
        nbtBytesIO.write(data)
        nbtBytesIO.seek(0) # fml i hate this shit, i have to seek to the beginning for it to work T-T

        nbtData: nbtlib.File = nbtlib.File.parse(nbtBytesIO)
        return nbtData

    # TODO: have the ability to modify the chunks and maybe save the region file back again



if __name__ == "__main__":
    r = Region("./world/overworld/r.0.0.mca")
    nbt = r.getChunkNBT(0, 0)
    #print(len(nbt["sections"]))

    p = nbt["sections"][0]["block_states"]["palette"]
    #print(p, len(p))

    for i in range(0, len(nbt["sections"])):
        print(nbt["sections"][i].keys(), nbt["sections"][i]["Y"]*16)
    #print(nbt.keys())