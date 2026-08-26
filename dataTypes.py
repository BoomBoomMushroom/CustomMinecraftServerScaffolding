import struct
import re
# For format strings for (un)packing check here: https://docs.python.org/3/library/struct.html#struct-format-strings

class BytesReader:
    def __init__(self, data: bytes, startPos: int=0):
        self.data = data
        self.bytesRead = startPos

    def readByte(self, incrementPointer: bool=True):
        b = self.data[self.bytesRead]
        if incrementPointer: self.bytesRead += 1
        return b

    def setPointer(self, newPointer: int): self.bytesRead = newPointer
    def incrementPointer(self, increment: int): self.bytesRead += increment

class BytesWriter:
    def __init__(self, data: bytes = bytes()):
        self.data: bytes = data
    
    def appendBytes(self, newBytes: bytes):
        self.data += newBytes

    def appendInt(self, v: int):
        self.data += bytes([v])

# Bit Sets
class BitSet:
    def __init__(self, data: list[bool]=None):
        # basically a big ol array of bits/bools
        self.data: list[bool] = data
        if self.data == None: self.data = []
    def append(self, val: bool=False): self.data.append(val)
    def pop(self) -> bool: return self.data.pop()
    def __len__(self) -> int: return len(self.data)
    def toLongArray(self) -> list[int]:
        longArr = []
        for _, bit in enumerate(self.data):
            # 8 bits * 8 bytes = how many bits until we reset
            if _ % (8*8) == 0: longArr.append(0)

            if bit:
                longArr[-1] |= 1 << (_%64)

        return longArr

def writeBitSet(bitSet: BitSet) -> bytes:
    outBytes = bytes()
    longs = bitSet.toLongArray()
    outBytes += writeVarInt(len(longs))
    for long in longs: outBytes += writeLong(long)
    return outBytes

# Var Ints
def readVarInt(data: bytes) -> tuple[int, int]: # value, bytesRead
    reader = BytesReader(data)
    value = 0

    for position in range(0, 32, 7):
        currentByte = reader.readByte()
        value |= (currentByte & 0x7F) << position
        if (currentByte & 0x80) == 0: return (value, reader.bytesRead)

    raise Exception("Varint too big")

def writeVarInt(value: int) -> bytes:
    writer = BytesWriter()
    while (value & ~0x7F) != 0:
        writer.appendInt( (value & 0x7F) | 0x80 )

        value >>= 7
    
    writer.appendInt(value & 0xFF)
    return writer.data

# Var Longs
def readVarLong(data: bytes) -> tuple[int, int]:
    return readVarInt(data)

def writeVarLong(value: int):
    return writeVarInt(value)


# strings
def readString(data: bytes) -> tuple[str, int]:
    length, bytesReadForLength = readVarInt(data)
    stringData: bytes = data[bytesReadForLength:bytesReadForLength+length]
    stringData = stringData.decode("utf-8")

    return (stringData, length + bytesReadForLength)

def writeString(toWrite: str) -> bytes:
    length = len(toWrite)
    lenBytes: bytes = writeVarInt(length)
    # I actually dont care if it is more or not
    #if len(lenBytes) > 3: raise Exception("Length of stringLength varint cannot be more than 3 bytes!")
    return lenBytes + toWrite.encode("utf-8")

# bytes
def writeUnsignedByte(value: int) -> bytes:
    return struct.pack(">B", value)
def writeByte(value: int) -> bytes:
    return struct.pack(">b", value)

def readByte(value: int) -> tuple[int, int]:
    val = struct.unpack(">b", value)[0]
    return (val, 1)

# prefixed byte array
def writePrefixedByteArray(values: list[int]) -> bytes:
    outBytes = bytes()
    outBytes += writeVarInt(len(values))
    for v in values: outBytes += writeByte(v)
    return outBytes

def writePrefixedUnsignedByteArray(values: list[int]) -> bytes:
    outBytes = bytes()
    outBytes += writeVarInt(len(values))
    for v in values: outBytes += writeUnsignedByte(v)
    return outBytes

# prefixed raw data array
def writePrefixedRawDataArray(values: list[bytes]) -> bytes:
    outBytes = bytes()
    outBytes += writeVarInt(len(values))
    for v in values: outBytes += v
    return outBytes

# shorts
def readUnsignedShort(data: bytes) -> tuple[int, int]:
    val = struct.unpack('>H', data[0:2])[0]
    return (val, 2)

def writeUnsignedShort(value: int) -> bytes:
    data = struct.pack('>H', value)
    return data

def readShort(data: bytes) -> tuple[int, int]:
    val = struct.unpack('>h', data[0:2])[0]
    return (val, 2)

def writeShort(value: int) -> bytes:
    data = struct.pack('>h', value)
    return data

# ints
def readInt(data: bytes) -> tuple[int, int]:
    val = struct.unpack('>i', data[0:4])[0]
    return (val, 4)
def writeInt(val: int) -> bytes:
    return struct.pack('>i', val)

# longs
def writeLong(value: int) -> bytes:
    return struct.pack(">q", value)

# floats
def writeFloat(value: float) -> bytes:
    return struct.pack(">f", value)

def readFloat(data: bytes) -> tuple[float, int]:
    val = struct.unpack(">f", data[0:4])[0]
    return (val, 4)

# doubles
def writeDouble(value: float) -> bytes:
    return struct.pack(">d", value)

def readDouble(data: bytes) -> tuple[float, int]:
    val = struct.unpack(">d", data[0:8])[0]
    return (val, 8)


# booleans
def writeBoolean(value: bool) -> bytes:
    if value == True: return bytes([0x01])
    else: return bytes([0x00])

# identifiers
def readIdentifier(data: bytes) -> tuple[str, int]:
    identifier, bytesRead = readString(data)
    namespace, value = identifier.split(":")

    namespaceMatch = re.fullmatch("[a-z0-9._-]+", namespace)
    valueMatch = re.fullmatch("[a-z0-9._/-]+", value)

    if namespaceMatch == None or valueMatch == None:
        raise Exception("Invalid Identifier!! " + identifier)


    return (identifier, bytesRead)

def writeIdentifier(identifier: str) -> bytes:
    b: bytes = writeString(identifier)
    readIdentifier(b) # if it is an invalid identifier it will raise an exception in here
    return b

# Positions

def writePosition(x: int, y: int, z: int) -> bytes:
    x <<= (12+26) # 12 for y, 26 for z
    y <<= 26 # 26 for z
    n = x | y | z # bit old 8 byete number (26+12+26=64 bits)
    return struct.pack('>q', n)


def reverseBits(value: int, bits: int=8) -> int:
    return int( ('{:0'+str(bits)+'b}').format(value)[::-1], 2)


if __name__ == "__main__":
    pass

