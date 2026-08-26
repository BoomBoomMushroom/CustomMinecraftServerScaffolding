from gameRules import GameRules

import json

class ServerSettings:
    version = "26.2"
    protocol = 776
    gameRules: GameRules = GameRules
    serverBrand: str = "CustomMCServerScaffolding" # default is "vanilla"

    maxPlayers: int = 20
    playersOnline: int = 0
    motd: str = "MOTD from Server, to modify it: change `ServerSettings.motd` in ServerSettings.py"
    serverIcon: str = "data:image/png;base64,<data>"

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




