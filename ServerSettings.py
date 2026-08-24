from gameRules import GameRules

import json

class ServerSettings:
    version = "26.2"
    protocol = 776
    gameRules: GameRules = GameRules

    maxPlayers: int = 20
    playersOnline: int = 0
    motd: str = "MOTD from Server, to modify it: change `ServerSettings.motd` in ServerSettings.py"
    serverIcon: str = "data:image/png;base64,<data>"

    registriesPath = "./registries/26.2/minecraft"
    registryTagsPath = "./registries/26.2/minecraft/tags"
    staticRegistriesFilePath = "./registries/26.2/registries.json"
    with open(staticRegistriesFilePath) as f:
        staticRegistries = json.load(f)


    @classmethod
    def getRegistryNamespaceList(cls, namespace: str) -> list[str]:
        return cls.staticRegistries.get(namespace)
    @classmethod
    def getRegistryData(cls, namespace: str, identifier: str) -> int:
        return cls.getRegistryNamespaceList(namespace)["entries"][identifier]["protocol_id"]




