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
    SCRAMBLER_TAP_1   = 19
    SCRAMBLER_TAP_2   = 0

    # nic_global_pkg constants
    IDLE_BLK = 0x1E
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

    CTRL_HDR = 0b01
    DATA_HDR = 0b10

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

    def bit_reverse_old(self, word):
        payload2 = 0
        for i in range(8):
            byte = (word >> (i * 8)) & 0xFF
            out_byte = 0
            for j in range(8):
                bit = (byte >> j) & 1
                out_byte |= bit << (7-j)
            payload2 |= out_byte << (i * 8)
        return payload2

    def bit_reverse(self, word):
        payload2 = 0
        for i in range(64):
            bit = (word >> i) & 1
            payload2 |= bit << (63 - i)
        return payload2

    async def send_idles(self, count: int):
        idle_payload = self._build_ctrl_payload(
            self.IDLE_BLK, [self.IDLE_BLK] * 7
        )
        for _ in range(count):
            # Scramble the idle payload just like data words
            await self._push_word(self.CTRL_HDR, self.scramble_64b(self.bit_reverse(idle_payload)))


    async def send_ethernet_frame(self, frame_bytes: list[int]):
        # SOF — scrambled
        sof_raw = self._build_ctrl_payload(self.SOF_L0, frame_bytes[:7])
        await self._push_word(self.CTRL_HDR, self.scramble_64b(self.bit_reverse(sof_raw)))

        # Data words — scrambled (already correct)
        remaining = frame_bytes[7:]
        while len(remaining) > 7:
            word = int.from_bytes(remaining[:8], "little")
            await self._push_word(self.DATA_HDR, self.scramble_64b(self.bit_reverse(word)))
            remaining = remaining[8:]

        # TERM — scrambled
        n_valid  = len(remaining)
        remaining.append(self.TERM_CODES[n_valid]) 
        for _ in range(7 - n_valid):
            remaining.append(self.IDLE_BLK);
        word2 = int.from_bytes(remaining[:8], "little")
        await self._push_word(self.CTRL_HDR, self.scramble_64b(self.bit_reverse(word2)))

    async def send_back_to_back_frames(
        self,
        frames: list[list[int]],
        gap_idles: int = 4
    ):
        for frame in frames:
            await self.send_ethernet_frame(frame)
            await self.send_idles(gap_idles)

    async def send_corrupted_frame(self, frame_bytes: list[int]):
        await self.send_ethernet_frame(frame_bytes)
        for _ in range(10):
            await self._push_word(0b00, 0xDEADBEEFDEADBEEF)

    async def send_random_bubbles(self, cycles: int, bubble_prob: float = 0.1):
        for _ in range(cycles):
            if random.random() < bubble_prob:
                await self.send_bubble()
            else:
                hdr = random.choice([self.CTRL_HDR, self.DATA_HDR])
                await self._push_word(hdr, random.getrandbits(64))

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