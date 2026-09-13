from world import World

from typing import Literal

EntityTypes = Literal["NONE", "PLAYER"]

class Entity:
    def __init__(self):
        self.UUID: bytes = None
        self.posX: float = 0
        self.posY: float = 0
        self.posZ: float = 0
        self.velX: float = 0
        self.velY: float = 0
        self.velZ: float = 0
        self.yaw: float = 0
        self.pitch: float = 0
        self.dimension: str = "overworld"
        self.onGround = False
        self.entityId: int = None
    
    def setPosition(self, x: float=0, y: float=0, z: float=0):
        self.posX = x
        self.posY = y
        self.posZ = z
    def setVelocity(self, x: float=0, y: float=0, z: float=0):
        self.velX = x
        self.velY = y
        self.velZ = z
    def setRotation(self, yaw: float=0, pitch: float=0):
        self.yaw = yaw
        self.pitch = pitch
    def setEID(self, eid: int):
        self.entityId = eid
    def setUUID(self, uuid: bytes):
        self.UUID = uuid



