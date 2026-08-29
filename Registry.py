import json
import threading
import os
import nbtlib
import io
import time

import dataTypes
from ServerSettings import ServerSettings

class TagsPacketForSyncedRegistry:
    packetData: bytes = None
    isGenerating = False

    @classmethod
    def init(cls):
        threadGeneratePacket = threading.Thread(target=cls._generatePacketData, args=(), daemon=True)
        threadGeneratePacket.start()

    @classmethod
    def _generatePacketData(cls):
        if cls.packetData != None: return
        if cls.isGenerating: return
        cls.isGenerating = True

        # registry tags
        queuedTagsRegistries = os.listdir(Registry.registryTagsPath)
        queuedTagsRegistries.remove("villager_trade")
        queuedTagsRegistries.remove("worldgen")

        tagIdentifiersToValues: dict[str, list[int]] = {}

        taggedRegistersEntries: list[bytes] = []
        while len(queuedTagsRegistries) > 0:
            skipTagRegister = False
            tagRegister = queuedTagsRegistries.pop(0)
            path = f"{Registry.registryTagsPath}/{tagRegister}"
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
                            idx = Registry.getSyncedRegistry(f"minecraft:{tagRegister}").getEntryIndex(value)
                        except (ValueError, FileNotFoundError) as e:
                            # if we get a FileNotFoundError then we tried to access a static registry as a synced one
                            try:
                                idx = Registry.staticRegistries[f"minecraft:{tagRegister}"]["entries"][value]["protocol_id"]
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

        cls.packetData = updateTagsPacketData
        cls.isGenerating = False

    @classmethod
    def waitUntilLoaded(self, maxWaitTime: float=60):
        timeout = 0
        while self.packetData == None:
            time.sleep(0.01)
            timeout += 0.01
            if timeout >= maxWaitTime: raise TimeoutError("Timed out while waiting for tag packet data to generate")

    @classmethod
    def getPacketData(cls) -> bytes:
        if cls.packetData == None: cls.init()
        cls.waitUntilLoaded()
        return cls.packetData

class SyncedRegistry:
    def __init__(self, register: str):
        # register should 100% not start with "minecraft:" because it is used for the folder lookup
        if register.startswith("minecraft:"): register = register.split("minecraft:")[1] # failsafe

        self.register: str = register
        self.namespace: str = f"minecraft:{register}"

        self.hasLoadedAllEntries = False
        self.entries: list[str] = []
        self.entriesToNBTBytes: dict[str, bytes] = {}

        # returns true if the folder exists
        if self.errorIfNotFolder():
            threadLoadEntries = threading.Thread(target=self._loadEntries, args=(), daemon=True)
            threadLoadEntries.start()

    def errorIfNotFolder(self) -> bool:
        path = f"{Registry.registriesPath}/{self.register}"
        if os.path.isdir(path): return True
        raise FileNotFoundError("Registry folder not found", path)

    def waitUntilLoaded(self, maxWaitTime: float=5):
        timeout = 0
        while self.hasLoadedAllEntries == False:
            time.sleep(0.01)
            timeout += 0.01
            if timeout >= maxWaitTime: raise TimeoutError("Timed out while waiting for registry entries to load", self.namespace)

    # move the loading into this function instead of getEntries so we can prevent race conditions & duplicate entries
    def _loadEntries(self):
        if self.hasLoadedAllEntries: return
        path = f"{Registry.registriesPath}/{self.register}"
                
        tagFiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        tagFiles: list[str] = [f for f in tagFiles if f.endswith(".json")]

        for file in tagFiles:
            nameNoExtention = ".".join( file.split(".")[:-1] )
            fileData = "{}"
            with open(f"{path}/{file}") as f: fileData = f.read()

            # load the json file data as NBT
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

            entryIdentifier = f"minecraft:{nameNoExtention}"
            self.entries.append(entryIdentifier) # make sure we don't lose track of the order!
            self.entriesToNBTBytes[entryIdentifier] = nbtBytes

        self.hasLoadedAllEntries = True
        return self.entries

    def getEntries(self) -> list[str]:
        self.waitUntilLoaded()
        return self.entries

    def getPacketData(self) -> bytes:
        self.waitUntilLoaded()

        packetData = bytes()
        packetData += dataTypes.writeIdentifier(self.namespace) # registry id
        packetData += dataTypes.writeVarInt(len(self.entries)) # lenth of entries array
        for entry in self.entries:
            packetData += dataTypes.writeIdentifier(entry) # name of the entry (already prefixed w/ "minecraft:")
            packetData += dataTypes.writeBoolean(True) # yes we have nbt data
            packetData += self.entriesToNBTBytes[entry] # the nbt entry data

        return packetData

    def getEntryIndex(self, entryIdentifier: str) -> int:
        self.waitUntilLoaded()
        return self.entries.index(entryIdentifier)

class Registry:
    registriesPath = "./registries/26.2/generated/data/minecraft"
    registryTagsPath = "./registries/26.2/generated/data/minecraft/tags"

    staticRegistriesFilePath = "./registries/26.2/generated/reports/registries.json"
    with open(staticRegistriesFilePath) as f:
        staticRegistries = json.load(f)

    blockStatesPaletteFilePath = "./registries/26.2/generated/reports/blocks.json"
    with open(blockStatesPaletteFilePath) as f:
        blockStatesPalette: dict[str, dict] = json.load(f)

    @classmethod
    def getBlockStateId(cls, blockIdentifier: str, properties: dict[str, str]={}) -> int:
        searchKeys: list[str] = list(properties.keys())

        default: int = None
        candidates: list[int] = []

        listOfStates: list[dict] = cls.blockStatesPalette[blockIdentifier]["states"]
        for state in listOfStates:
            isMatching = True
            stateId = state["id"]
            isDefault: bool = state.get("default", False)
            if isDefault:
                default = stateId
                if len(searchKeys) == 0: return default # we found what we wanted!

            if len(searchKeys) == 0: continue
            stateProperties: dict[str, str] = state["properties"]
            for refKey in searchKeys:
                if properties[refKey] == stateProperties[refKey]: continue
                # if here then the property didn't match D:
                isMatching = False
                break

            if isMatching == False: continue
            candidates.append(stateId)

        if len(candidates) == 0: raise Exception("Could not find any candidates w/ the desired properties!")
        if len(candidates) > 1: raise Exception("Too many matches, try narrowing your search!")
        return candidates[0]

    @classmethod
    def getRegistryNamespaceList(cls, namespace: str) -> list[str]:
        return cls.staticRegistries.get(namespace)
    @classmethod
    def getRegistryData(cls, namespace: str, identifier: str) -> int:
        return cls.getRegistryNamespaceList(namespace)["entries"][identifier]["protocol_id"]

    syncedRegistries: dict[str, SyncedRegistry] = {}
    @classmethod
    def getSyncedRegistry(cls, register: str):
        syncedReg = cls.syncedRegistries.get(register, None)
        if syncedReg == None:
            syncedReg = SyncedRegistry(register)
            cls.syncedRegistries[register] = syncedReg
        
        return syncedReg

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
    _neededSyncedRegistries = ["enchantment", "jukebox_song", "test_instance", "wolf_variant", "test_environment", "chicken_sound_variant", "cow_sound_variant", "pig_sound_variant", "dimension_type", "enchantment_provider", "enchantment_provider/raid", "sulfur_cube_archetype", "cat_variant", "cow_variant", "chat_type", "frog_variant", "damage_type", "worldgen", "worldgen/structure", "worldgen/world_preset", "worldgen/biome", "worldgen/placed_feature", "worldgen/structure_set", "worldgen/noise_settings", "worldgen/processor_list", "worldgen/configured_feature", "worldgen/multi_noise_biome_source_parameter_list", "worldgen/flat_level_generator_preset", "worldgen/noise", "worldgen/noise/nether", "worldgen/configured_carver", "banner_pattern", "zombie_nautilus_variant", "world_clock", "painting_variant", "cat_sound_variant", "wolf_sound_variant", "timeline", "dialog", "chicken_variant", "pig_variant", "trim_pattern", "instrument", "trim_material"]
    @classmethod
    def preloadRequriedSyncedRegistries(cls):
        [ cls.getSyncedRegistry(reg) for reg in cls._neededSyncedRegistries ] # preloads them


if __name__ == "__main__":
    a = Registry.getSyncedRegistry("minecraft:world_clock").getEntries()
    print(a)
    
    pass