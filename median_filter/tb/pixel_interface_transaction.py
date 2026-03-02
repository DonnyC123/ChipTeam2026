from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray

PIXEL_W = 8


PIXEL_TOTAL_W = PIXEL_W * 3  # 24 bits for packed {red, green, blue}


def _to_unsigned_safe(la: LogicArray, width: int = PIXEL_W) -> int:
    """Convert LogicArray to int; use 0 if it contains X/Z."""
    try:
        return la.to_unsigned() & ((1 << width) - 1)
    except (ValueError, TypeError):
        return 0


@dataclass
class PixelStruct:
    red: LogicArray = field(default_factory=lambda: LogicArray("X" * PIXEL_W))
    green: LogicArray = field(default_factory=lambda: LogicArray("X" * PIXEL_W))
    blue: LogicArray = field(default_factory=lambda: LogicArray("X" * PIXEL_W))

    @property
    def value_tuple(self):
        return (
            _to_unsigned_safe(self.red),
            _to_unsigned_safe(self.green),
            _to_unsigned_safe(self.blue),
        )

    def to_logic_array(self) -> LogicArray:
        """Packed as in RTL pixel_t: red=[7:0], green=[15:8], blue=[23:16]."""
        mask = (1 << PIXEL_W) - 1
        v = (
            _to_unsigned_safe(self.red)
            | (_to_unsigned_safe(self.green) << PIXEL_W)
            | (_to_unsigned_safe(self.blue) << (2 * PIXEL_W))
        )
        return LogicArray(v, PIXEL_TOTAL_W)

    @classmethod
    def from_logic_array(cls, la: LogicArray) -> "PixelStruct":
        """Unpack 24-bit LogicArray into red, green, blue (RTL order)."""
        mask = (1 << PIXEL_W) - 1
        try:
            u = la.to_unsigned()
        except (ValueError, TypeError):
            u = 0
        return cls(
            red=LogicArray(u & mask, PIXEL_W),
            green=LogicArray((u >> PIXEL_W) & mask, PIXEL_W),
            blue=LogicArray((u >> (2 * PIXEL_W)) & mask, PIXEL_W),
        )


@dataclass
class PixelInterfaceTransaction:
    pixel: PixelStruct = field(default_factory=PixelStruct)
    valid: Logic = field(default_factory=lambda: Logic(0))
