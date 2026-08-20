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