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
DIFFICULTY_EnumFrom: dict[int, DIFFICULTY] = {
    0: "PEACEFUL",
    1: "EASY",
    2: "NORMAL",
    3: "HARD",
}

GAMEMODE = Literal["NULL", "SURVIVAL", "CREATIVE", "ADVENTURE", "SPECTATOR"]
GAMEMODE_Enum: dict[GAMEMODE, int] = {
    "NULL": -1,
    "SURVIVAL": 0,
    "CREATIVE": 1,
    "ADVENTURE": 2,
    "SPECTATOR": 3,
}
GAMEMODE_EnumFrom: dict[int, GAMEMODE] = {
    1: "NULL",
    0: "SURVIVAL",
    1: "CREATIVE",
    2: "ADVENTURE",
    3: "SPECTATOR",
}

HEIGHTMAP_TYPE = Literal["WORLD_SURFACE", "MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES", "OCEAN_FLOOR"]
HEIGHTMAP_TYPE_Enum: dict[HEIGHTMAP_TYPE, int] = {
    "WORLD_SURFACE": 1,
    "MOTION_BLOCKING": 4,
    "MOTION_BLOCKING_NO_LEAVES": 5,
    "OCEAN_FLOOR": None, # idk it or it doesn't have one
}

ACTION_ID = Literal["PREFORM_RESPAWN", "REQUEST_STATS", "REQUEST_GAMERULE_VALUES"]
ACTION_ID_Enum: dict[ACTION_ID, int] = {
    "PREFORM_RESPAWN": 0,
    "REQUEST_STATS": 1,
    "REQUEST_GAMERULE_VALUES": 2,
}
ACTION_ID_EnumFrom: dict[int, ACTION_ID] = {
    0: "PREFORM_RESPAWN",
    1: "REQUEST_STATS",
    2: "REQUEST_GAMERULE_VALUES",
}

PLAYER_INFO_UPDATE_ACTIONS = Literal["AddPlayer", "InitializeChat", "UpdateGameMode", "UpdateListed", "UpdateLatency", "UpdateDisplayName", "UpdateListPriority", "UpdateHat"]

# https://minecraft.wiki/w/Java_Edition_protocol/Packets#Game_Event
GAME_EVENT_ID = Literal[
    "NO_RESPAWN_BLOCK_AVAILABLE", # displays you have no home bed or it was obstructed
    "BEGIN_RAINING", # actually stops the rain, use change rain level instead (sets rain level = 0)
    "END_RAINING", # actually starts the rain (sets rain level = 1)
    "CHANGE_GAME_MODE", # values use the GAMEMODE enums from above to know which one to use
    "WIN_GAME", # roll the credits
    "DEMO_EVENT", # values of 0=show welcome demo screen, 101=tell movement, 102=tell jump, 103=tell inventory, 104=tell demo over and to take a screen shot
    "PLAY_ARROW_HIT_SOUND",
    "CHANGE_RAIN_LEVEL", # value for rain level ranges from 0 to 1
    "CHANGE_THUNDER_LEVEL", # value for thunder level ranges from 0 to 1, doesn't start raining
    "PLAY_PUFFERFISH_STING_SOUND",
    "PLAY_ELDER_GUARDIAN_JUMP_SCARE", # 0 = visual effect only, 1 = sound + visual effect
    "TOGGLE_IMMEDIATE_RESPAWN", # 0 = enable respawn screen, 1 = immediate respawn ; linked to the `doImmediateRespawn` gamerule
    "TOGGLE_LIMITED_CRAFTING", # 0 = disable limited crafting, 1 = enable limited crafting ; linked to the `doLimitedCrafting` gamerule
    "START_WAITING_FOR_CHUNKS"
]
GAME_EVENT_ID_ENUM: dict[GAME_EVENT_ID, int] = {
    "NO_RESPAWN_BLOCK_AVAILABLE": 0,
    "BEGIN_RAINING": 1,
    "END_RAINING": 2,
    "CHANGE_GAME_MODE": 3,
    "WIN_GAME": 4,
    "DEMO_EVENT": 5,
    "PLAY_ARROW_HIT_SOUND": 6,
    "CHANGE_RAIN_LEVEL": 7,
    "CHANGE_THUNDER_LEVEL": 8,
    "PLAY_PUFFERFISH_STING_SOUND": 9,
    "PLAY_ELDER_GUARDIAN_JUMP_SCARE": 10,
    "TOGGLE_IMMEDIATE_RESPAWN": 11,
    "TOGGLE_LIMITED_CRAFTING": 12,
    "START_WAITING_FOR_CHUNKS": 13,
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

