import json

class ServerSettings:
    version = "26.2"
    protocol = 776

    maxPlayers: int = 20
    playersOnline: int = 0
    motd: str = "MOTD from Server, to modify it: change `ServerSettings.motd` in ServerSettings.py"
    serverIcon: str = "data:image/png;base64,<data>"

    registriesPath = "./registries/26.2/minecraft"
    registryTagsPath = "./registries/26.2/minecraft/tags"
    staticRegistriesFilePath = "./registries/26.2/registries.json"
    with open(staticRegistriesFilePath) as f:
        staticRegistries = json.load(f)


    def __init__(self):
        pass

