from itertools import count
from tb_utils.generic_sequence import GenericSequence
from rx_tb.tb.rx_sequence_item import RxSequenceItem
import random

class BitStream:
    def __init__(self):
        self._bits: int = 0  
        self._len:  int = 0 

    def push_66b(self, header: int, payload: int):
        word = (header << 64) | (payload & 0xFFFFFFFFFFFFFFFF)
        self._bits |= (word << self._len)
        self._len  += 66

    def pop_64b_chunks(self) -> list[int]:
        chunks = []
        while self._len >= 64:
            chunks.append(self._bits & 0xFFFFFFFFFFFFFFFF)
            self._bits >>= 64
            self._len  -= 64
        return chunks

    def flush_partial(self) -> tuple[int, int] | None:
        if self._len == 0:
            return None
        return (self._bits & 0xFFFFFFFFFFFFFFFF, self._len)


class RxSequence(GenericSequence):

    SCRAMBLER_STATE_W = 58
    SCRAMBLER_TAP_1   = 38
    SCRAMBLER_TAP_2   = 57

    # nic_global_pkg constants
    IDLE_BLK = 0x1E
    IDLE_BLK_C = 0x00
    SOF_L0   = 0x78
    SOF_L4   = 0x33
    TERM_CODES = [
        0x87,  # TERM_L0: 0 valid data bytes
        0x99,  # TERM_L1: 1 valid data bytes
        0xAA,  # TERM_L2: 2 valid data bytes
        0xB4,  # TERM_L3: 3 valid data bytes
        0xCC,  # TERM_L4: 4 valid data bytes
        0xD2,  # TERM_L5: 5 valid data bytes
        0xE1,  # TERM_L6: 6 valid data bytes
        0xFF,  # TERM_L7: 7 valid data bytes
    ]

    CTRL_HDR = 0b10
    DATA_HDR = 0b01

    def __init__(self, driver):
        super().__init__(driver)
        self.scrambler_state = (1 << self.SCRAMBLER_STATE_W) - 1
        self._stream = BitStream()

    async def _push_word(self, header: int, payload_64: int):
        self._stream.push_66b(header, payload_64)
        for chunk in self._stream.pop_64b_chunks():
            await self._drive_64b(chunk, valid=True)

    async def _drive_64b(self, data: int, valid: bool = True):
        item = RxSequenceItem.from_int(data, valid=valid)
        await self.add_transaction(item)

    async def _flush_stream(self):
        partial = self._stream.flush_partial()
        if partial is not None:
            value, _ = partial
            await self._drive_64b(value, valid=True)

    def _build_ctrl_payload(self, ctrl_byte: int, data_bytes: list[int]) -> int:
        assert len(data_bytes) <= 7
        padded = data_bytes + [0] * (7 - len(data_bytes))
        word = ctrl_byte
        for i, b in enumerate(padded):
            word |= (b & 0xFF) << ((i+1) * 8)
        return word

    async def send_bubble(self):
        await self._flush_stream()
        await self._drive_64b(0, valid=False)

    def bit_reverse(self, word):
        payload2 = 0
        for i in range(64):
            bit = (word >> i) & 1
            payload2 |= bit << (63 - i)
        return payload2

    async def send_idles(self, count: int):
        idle_payload = self._build_ctrl_payload(
            self.IDLE_BLK, [self.IDLE_BLK_C] * 7
        )
        for _ in range(count):
            await self._push_word(self.CTRL_HDR, self.scramble_64b(idle_payload))

    async def send_ethernet_frame(self, frame_bytes: list[int]):
        await self.notify_subscribers({"frame": list(frame_bytes)})

        sof_raw = self._build_ctrl_payload(self.SOF_L0, frame_bytes[:7])
        await self._push_word(self.CTRL_HDR, self.scramble_64b(sof_raw))

        remaining = frame_bytes[7:]
        while len(remaining) > 7:
            word = int.from_bytes(remaining[:8], "little")
            await self._push_word(self.DATA_HDR, self.scramble_64b(word))
            remaining = remaining[8:]

        n_valid  = len(remaining)
        term_raw = self._build_ctrl_payload(self.TERM_CODES[n_valid], remaining)
        await self._push_word(self.CTRL_HDR, self.scramble_64b(term_raw))

    async def send_back_to_back_frames(
        self,
        frames: list[list[int]],
        gap_idles: int = 4
    ):
        for frame in frames:
            await self.send_ethernet_frame(frame)
            await self.send_idles(gap_idles)

    def scramble_64b(self, input_word: int) -> int:
        scrambled = 0
        state = self.scrambler_state
        for i in range(64):
            in_bit   = (input_word >> i) & 1
            feedback = ((state >> self.SCRAMBLER_TAP_1) ^ (state >> self.SCRAMBLER_TAP_2)) & 1
            out_bit  = in_bit ^ feedback
            scrambled |= (out_bit << i)
            state    = ((state << 1) | out_bit) & ((1 << self.SCRAMBLER_STATE_W) - 1)
        self.scrambler_state = state
        return scrambled
    
    async def send_invalid_blocks(self, count: int = 10):
        for _ in range(count):
            await self._push_word(0b00, random.getrandbits(64))