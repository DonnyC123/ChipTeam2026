from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from random import randint
from typing import Self
from cocotb.types import LogicArray, Logic


@dataclass
class AbstractTransaction(ABC):
    def randomize(self):
        for f in fields(self):
            curr_val = getattr(self, f.name)
            if isinstance(curr_val, LogicArray):
                max_val = (1 << len(curr_val)) - 1
                random_val = randint(0, max_val)
                setattr(self, f.name, LogicArray(random_val, curr_val.range))
            elif f.type == Logic:
                random_val = randint(0, 1)
                setattr(self, f.name, Logic(random_val))

    def __str__(self):
        str = ""
        for name, value in vars(self).items():
            str += f"{name} : 0x {value:02x}"
        return str

    @classmethod
    @abstractmethod
    def invalid_seq_item(cls) -> Self:
        pass


@dataclass
class AbstractValidTransaction(AbstractTransaction):
    @property
    @abstractmethod
    def valid(self) -> bool:
        pass

    @valid.setter
    @abstractmethod
    def valid(self, value: bool):
        pass
