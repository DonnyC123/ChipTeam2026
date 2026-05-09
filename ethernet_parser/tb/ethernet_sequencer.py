import random
from typing import Literal

from ethernet_parser.tb.ethernet_parser_sequence_item import (
    EthernetParserSequenceItem,
)
from tb_utils.generic_sequence import GenericSequence


class EthernetParserSequence(GenericSequence):
    MIN_FRAME_BYTES = 64
    DATA_BYTES = EthernetParserSequenceItem.BYTES_OUT
    DATA_MASK = (1 << EthernetParserSequenceItem.DATA_IN_W) - 1
    FULL_MASK = (1 << DATA_BYTES) - 1

    ETHERTYPE_OFFSET = 12
    ETHERTYPE_IPV4   = (0x00, 0x08)
    ETHERTYPE_IPV6   = (0xDD, 0x86)
    ETHERTYPE_OTHER  = (0x34, 0x12)

    SOF0_BYTES      = 7
    SOF0_START_LANE = 1
    SOF0_MASK       = 0b1111_1110

    SOF4_BYTES      = 3
    SOF4_START_LANE = 5
    SOF4_MASK       = 0b1110_0000
    START_MODE_CONFIGS = {
        "sof0": {
            "start_count": SOF0_BYTES,
            "start_lane": SOF0_START_LANE,
            "start_mask": SOF0_MASK,
            "parse_result_item_idx": 1,
        },
        "sof4": {
            "start_count": SOF4_BYTES,
            "start_lane": SOF4_START_LANE,
            "start_mask": SOF4_MASK,
            "parse_result_item_idx": 2,
        },
    }

    def __init__(self, driver):
        super().__init__(driver)
        self.frame: list[int] = []

    @staticmethod
    def _resolve_rng(
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> random.Random:
        if rng is not None:
            return rng
        return random.Random(seed)

    def _validate_frame(self, frame_bytes: list[int]) -> list[int]:
        frame = list(frame_bytes)
        if len(frame) < self.MIN_FRAME_BYTES:
            raise ValueError(
                f"frame length must be at least {self.MIN_FRAME_BYTES} bytes"
            )

        for idx, byte in enumerate(frame):
            try:
                byte_value = int(byte)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"frame byte at index {idx} is not an integer") from exc

            if not 0 <= byte_value <= 0xFF:
                raise ValueError(
                    f"frame byte at index {idx} must be in range 0..255"
                )

            frame[idx] = byte_value

        return frame

    def _require_frame(self) -> list[int]:
        if not self.frame:
            raise ValueError(
                "frame is not set; call set_random_frame or set_manual_frame"
            )
        return self.frame

    def set_random_frame(
        self,
        length: int,
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> list[int]:
        if length < self.MIN_FRAME_BYTES:
            raise ValueError(
                f"frame length must be at least {self.MIN_FRAME_BYTES} bytes"
            )

        local_rng = self._resolve_rng(rng=rng, seed=seed)
        self.frame = [local_rng.randrange(256) for _ in range(length)]
        return list(self.frame)

    def set_manual_frame(self, frame_bytes: list[int]) -> list[int]:
        self.frame = self._validate_frame(frame_bytes)
        return list(self.frame)

    def set_ethertype(self, kind: str):
        frame = self._require_frame()
        if not isinstance(kind, str):
            raise ValueError("Ethertype kind must be a string")

        normalized = kind.upper()
        if normalized == "IPV4":
            ethertype = self.ETHERTYPE_IPV4
        elif normalized == "IPV6":
            ethertype = self.ETHERTYPE_IPV6
        elif normalized == "OTHER":
            ethertype = self.ETHERTYPE_OTHER
        else:
            raise ValueError("Ethertype kind must be IPV4, IPV6, or OTHER")

        frame[self.ETHERTYPE_OFFSET : self.ETHERTYPE_OFFSET + 2] = list(ethertype)
        if tuple(frame[self.ETHERTYPE_OFFSET : self.ETHERTYPE_OFFSET + 2]) != ethertype:
            raise ValueError("failed to set Ethertype bytes in frame")

    def _expected_output_from_frame(self) -> int:
        frame = self._require_frame()
        ethertype = tuple(frame[self.ETHERTYPE_OFFSET : self.ETHERTYPE_OFFSET + 2])
        if ethertype == self.ETHERTYPE_IPV4:
            return EthernetParserSequenceItem.OUTPUT_IPV4
        if ethertype == self.ETHERTYPE_IPV6:
            return EthernetParserSequenceItem.OUTPUT_IPV6
        return EthernetParserSequenceItem.OUTPUT_OTHER

    def _resolve_start_mode(
        self, start_mode: Literal["sof0", "sof4"]
    ) -> dict[str, int]:
        normalized_mode = start_mode.lower()
        if normalized_mode not in self.START_MODE_CONFIGS:
            raise ValueError("start_mode must be 'sof0' or 'sof4'")
        return self.START_MODE_CONFIGS[normalized_mode]

    async def _drive_word(
        self,
        data: int,
        bytes_valid: int,
        expected_output: int,
        expected_payload_time: bool = False,
        valid: bool = True,
    ):
        item = EthernetParserSequenceItem(
            bytes_valid_i=bytes_valid & self.FULL_MASK,
            data_i=data & self.DATA_MASK,
            expected_payload_time_o=expected_payload_time,
            expected_outputs_o=expected_output,
        )
        item.valid = valid
        await self.notify_subscribers(item.to_data)
        await self.add_transaction(item)

    def _pack_bytes(self, bytes_chunk: list[int], start_lane: int) -> int:
        if start_lane < 0 or start_lane >= self.DATA_BYTES:
            raise ValueError("start_lane must be in range 0..7")
        if start_lane + len(bytes_chunk) > self.DATA_BYTES:
            raise ValueError("bytes_chunk does not fit in a 64-bit word")

        word = 0
        for offset, byte in enumerate(bytes_chunk):
            word |= (byte & 0xFF) << ((start_lane + offset) * 8)
        return word

    def _tail_mask(self, valid_bytes: int) -> int:
        if not 0 <= valid_bytes < self.DATA_BYTES:
            raise ValueError("valid_bytes must be in range 0..7")
        if valid_bytes == 0:
            return 0
        return ((1 << valid_bytes) - 1) << 1

    async def _drive_frame(
        self,
        *,
        start_count: int,
        start_lane: int,
        start_mask: int,
        expected_outputs_overrides: dict[int, int] | None = None,
        expected_payload_time_overrides: dict[int, bool] | None = None,
    ):
        frame = self._require_frame()
        expected_outputs_overrides = expected_outputs_overrides or {}
        expected_payload_time_overrides = expected_payload_time_overrides or {}
        item_idx = 0

        await self._drive_word(
            self._pack_bytes(frame[:start_count], start_lane),
            start_mask,
            expected_outputs_overrides.get(
                item_idx, EthernetParserSequenceItem.OUTPUT_OTHER
            ),
            expected_payload_time=expected_payload_time_overrides.get(item_idx, False),
            valid=True,
        )
        item_idx += 1

        remaining = frame[start_count:]
        while len(remaining) >= self.DATA_BYTES:
            await self._drive_word(
                self._pack_bytes(remaining[: self.DATA_BYTES], 0),
                self.FULL_MASK,
                expected_outputs_overrides.get(
                    item_idx, EthernetParserSequenceItem.OUTPUT_OTHER
                ),
                expected_payload_time=expected_payload_time_overrides.get(
                    item_idx, False
                ),
                valid=True,
            )
            remaining = remaining[self.DATA_BYTES :]
            item_idx += 1

        if remaining:
            await self._drive_word(
                self._pack_bytes(remaining, 1),
                self._tail_mask(len(remaining)),
                expected_outputs_overrides.get(
                    item_idx, EthernetParserSequenceItem.OUTPUT_OTHER
                ),
                expected_payload_time=expected_payload_time_overrides.get(
                    item_idx, False
                ),
                valid=True,
            )

    async def send_bubble(self):
        await self._drive_word(
            0,
            0,
            EthernetParserSequenceItem.OUTPUT_OTHER,
            valid=False,
        )

    async def send_idles(self, count: int):
        if count < 0:
            raise ValueError("count must be non-negative")
        for _ in range(count):
            await self.send_bubble()

    async def send_ethernet_frame(self, frame_bytes: list[int]):
        self.set_manual_frame(frame_bytes)
        await self.sof0_driver()

    async def send_IPV6_ethernet(
        self,
        frame_bytes: list[int],
        start_mode: Literal["sof0", "sof4"] = "sof0",
    ):
        self.set_manual_frame(frame_bytes)
        self.set_ethertype("IPV6")
        start_config = self._resolve_start_mode(start_mode)
        if (
            tuple(
                self.frame[self.ETHERTYPE_OFFSET : self.ETHERTYPE_OFFSET + 2]
            )
            != self.ETHERTYPE_IPV6
        ):
            raise ValueError("IPV6 Ethertype bytes must be [0xDD, 0x86]")
        if self._expected_output_from_frame() != EthernetParserSequenceItem.OUTPUT_IPV6:
            raise ValueError("expected_outputs_o must resolve to OUTPUT_IPV6")
        await self._drive_frame(
            start_count=start_config["start_count"],
            start_lane=start_config["start_lane"],
            start_mask=start_config["start_mask"],
            expected_outputs_overrides={
                start_config["parse_result_item_idx"]: EthernetParserSequenceItem.OUTPUT_IPV6
            },
            expected_payload_time_overrides={
                start_config["parse_result_item_idx"]: True
            },
        )

    async def send_IPV4_ethernet(
        self,
        frame_bytes: list[int],
        start_mode: Literal["sof0", "sof4"] = "sof0",
    ):
        self.set_manual_frame(frame_bytes)
        self.set_ethertype("IPV4")
        start_config = self._resolve_start_mode(start_mode)
        if (
            tuple(
                self.frame[self.ETHERTYPE_OFFSET : self.ETHERTYPE_OFFSET + 2]
            )
            != self.ETHERTYPE_IPV4
        ):
            raise ValueError("IPV4 Ethertype bytes must be [0x00, 0x08]")
        if self._expected_output_from_frame() != EthernetParserSequenceItem.OUTPUT_IPV4:
            raise ValueError("expected_outputs_o must resolve to OUTPUT_IPV4")
        await self._drive_frame(
            start_count=start_config["start_count"],
            start_lane=start_config["start_lane"],
            start_mask=start_config["start_mask"],
            expected_outputs_overrides={
                start_config["parse_result_item_idx"]: EthernetParserSequenceItem.OUTPUT_IPV4
            },
            expected_payload_time_overrides={
                start_config["parse_result_item_idx"]: True
            },
        )

    async def send_back_to_back_frames(
        self,
        frames: list[list[int]],
        gap_idles: int = 4,
    ):
        if gap_idles < 0:
            raise ValueError("gap_idles must be non-negative")

        for frame in frames:
            await self.send_ethernet_frame(frame)
            await self.send_idles(gap_idles)

    async def sof0_driver(self):
        await self._drive_frame(
            start_count=self.SOF0_BYTES,
            start_lane=self.SOF0_START_LANE,
            start_mask=self.SOF0_MASK,
            expected_payload_time_overrides={
                1: True,
            },
        )

    async def sof4_driver(self):
        await self._drive_frame(
            start_count=self.SOF4_BYTES,
            start_lane=self.SOF4_START_LANE,
            start_mask=self.SOF4_MASK,
            expected_payload_time_overrides={
                2: True,
            },
        )

    async def send_invalid_blocks(self, count: int = 10):
        if count < 0:
            raise ValueError("count must be non-negative")

        for _ in range(count):
            await self._drive_word(
                random.getrandbits(EthernetParserSequenceItem.DATA_IN_W),
                0,
                EthernetParserSequenceItem.OUTPUT_OTHER,
                valid=False,
            )
 
