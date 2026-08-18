class ServerSettings:
    version = "26.2"
    protocol = 776

    maxPlayers: int = 20
    playersOnline: int = 0
    motd: str = "MOTD from Server, to modify it: change `ServerSettings.motd` in ServerSettings.py"
    serverIcon: str = "data:image/png;base64,<data>"
    

    def __init__(self):
        pass

