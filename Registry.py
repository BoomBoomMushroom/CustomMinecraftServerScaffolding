import json
import threading
import os
import nbtlib
import io
import time

import dataTypes
from ServerSettings import ServerSettings

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

    @classmethod
    def preloadRequriedSyncedRegistries(cls):
        neededSyncedRegistries = ["enchantment", "jukebox_song", "test_instance", "wolf_variant", "test_environment", "chicken_sound_variant", "cow_sound_variant", "pig_sound_variant", "dimension_type", "enchantment_provider", "enchantment_provider/raid", "sulfur_cube_archetype", "cat_variant", "cow_variant", "chat_type", "frog_variant", "damage_type", "worldgen", "worldgen/structure", "worldgen/world_preset", "worldgen/biome", "worldgen/placed_feature", "worldgen/structure_set", "worldgen/noise_settings", "worldgen/processor_list", "worldgen/configured_feature", "worldgen/multi_noise_biome_source_parameter_list", "worldgen/flat_level_generator_preset", "worldgen/noise", "worldgen/noise/nether", "worldgen/configured_carver", "banner_pattern", "zombie_nautilus_variant", "world_clock", "painting_variant", "cat_sound_variant", "wolf_sound_variant", "timeline", "dialog", "chicken_variant", "pig_variant", "trim_pattern", "instrument", "trim_material"]
        [ cls.getSyncedRegistry(reg) for reg in neededSyncedRegistries ] # preloads them


if __name__ == "__main__":
    a = Registry.getSyncedRegistry("minecraft:world_clock").getEntries()
    print(a)
    
    pass