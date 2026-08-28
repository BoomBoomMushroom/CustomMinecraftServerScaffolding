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
    serverIcon: str = "data:image/png;base64,<data>" # image data as base64, rn its just garbage data




