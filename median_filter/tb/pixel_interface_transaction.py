from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray

PIXEL_W = 8


@dataclass
class PixelStruct:
    red: LogicArray = field(default_factory=lambda: LogicArray("X" * PIXEL_W))
    green: LogicArray = field(default_factory=lambda: LogicArray("X" * PIXEL_W))
    blue: LogicArray = field(default_factory=lambda: LogicArray("X" * PIXEL_W))

    @property
    def value_tuple(self):
        return (self.red.integer, self.green.integer, self.blue.integer)


@dataclass
class PixelInterfaceTransaction:
    pixel: PixelStruct = field(default_factory=PixelStruct)
    valid: Logic = field(default_factory=lambda: Logic(0))
