from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction

@dataclass # <--- CRITICAL: This must be here
class descramblerSequenceItem(AbstractTransaction):
    x_64b_i:       LogicArray = field(default_factory=lambda: LogicArray("0" * 64))
    valid_i:       Logic      = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> "descramblerSequenceItem":
        return cls(
            x_64b_i       = LogicArray("0" * 64),
            valid_i       = Logic(0)
        )

    @property
    def valid(self) -> bool:
        return bool(self.valid_i)
    
    @property
    def to_data(self):
        # Ensure this returns the dataclass instance itself
        return self