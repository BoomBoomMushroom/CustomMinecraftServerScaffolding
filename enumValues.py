from typing import Literal

BoundDirection = Literal["ServerBound", "ClientBound"]
ConnectionState = Literal["HANDSHAKING", "STATUS", "LOGIN", "CONFIGURATION", "PLAY"]

DIFFICULTY = Literal["PEACEFUL", "EASY", "NORMAL", "HARD"]
DIFFICULTY_Enum: dict[DIFFICULTY, int] = {
    "PEACEFUL": 0,
    "EASY": 1,
    "NORMAL": 2,
    "HARD": 3,
}

GAMEMODE = Literal["NULL", "SURVIVAL", "CREATIVE", "ADVENTURE", "SPECTATOR"]
GAMEMODE_Enum: dict[DIFFICULTY, int] = {
    "NULL": -1,
    "SURVIVAL": 0,
    "CREATIVE": 1,
    "ADVENTURE": 2,
    "SPECTATOR": 3,
}

HEIGHTMAP_TYPE = Literal["WORLD_SURFACE", "MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES", "OCEAN_FLOOR"]
HEIGHTMAP_TYPE_Enum: dict[HEIGHTMAP_TYPE, int] = {
    "WORLD_SURFACE": 1,
    "MOTION_BLOCKING": 4,
    "MOTION_BLOCKING_NO_LEAVES": 5,
    "OCEAN_FLOOR": None, # idk it or it doesnt have one
}






class textColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

