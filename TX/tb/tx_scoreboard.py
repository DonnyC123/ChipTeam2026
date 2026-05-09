class Raw66bParser:
    CTRL_HDR = 0b10
    DATA_HDR = 0b01

    IDLE_BLK = 0x1E
    SOF_L0 = 0x78
    SOF_L4 = 0x33
    TERM_TO_VALID = {
        0x87: 0,
        0x99: 1,
        0xAA: 2,
        0xB4: 3,
        0xCC: 4,
        0xD2: 5,
        0xE1: 6,
        0xFF: 7,
    }

    def __init__(self):
        self._bits = 0
        self._bit_count = 0
        self.frames: list[list[int]] = []
        self._current_frame: list[int] = []
        self._in_frame = False
        self.bad_blocks: list[tuple[int, int]] = []
        self.block_count = 0

    def ingest_raw64(self, raw: int):
        self._bits |= (raw & 0xFFFFFFFFFFFFFFFF) << self._bit_count
        self._bit_count += 64

        while self._bit_count >= 66:
            word = self._bits & ((1 << 66) - 1)
            self._bits >>= 66
            self._bit_count -= 66
            header = (word >> 64) & 0x3
            payload = word & 0xFFFFFFFFFFFFFFFF
            self.ingest_66b(header, payload)

    def ingest_66b(self, header: int, payload: int):
        self._parse_66b(header & 0x3, payload & 0xFFFFFFFFFFFFFFFF)
        self.block_count += 1

    def _parse_66b(self, header: int, payload: int):
        payload_bytes = list(payload.to_bytes(8, "little"))

        if header == self.DATA_HDR:
            if self._in_frame:
                self._current_frame.extend(payload_bytes)
            return

        if header != self.CTRL_HDR:
            self.bad_blocks.append((header, payload))
            self._drop_partial_frame()
            return

        block_type = payload_bytes[0]
        if block_type == self.IDLE_BLK:
            return

        if block_type == self.SOF_L0:
            self._start_frame(payload_bytes[1:8])
            return

        if block_type == self.SOF_L4:
            self._start_frame(payload_bytes[5:8])
            return

        if block_type in self.TERM_TO_VALID:
            if self._in_frame:
                valid_count = self.TERM_TO_VALID[block_type]
                self._current_frame.extend(payload_bytes[1 : 1 + valid_count])
                self._finish_frame()
            return

        self.bad_blocks.append((header, payload))
        self._drop_partial_frame()

    def _start_frame(self, first_bytes: list[int]):
        if self._in_frame:
            self.bad_blocks.append((self.CTRL_HDR, self.SOF_L0))
        self._current_frame = list(first_bytes)
        self._in_frame = True

    def _finish_frame(self):
        self.frames.append(list(self._current_frame))
        self._current_frame = []
        self._in_frame = False

    def _drop_partial_frame(self):
        self._current_frame = []
        self._in_frame = False

    @property
    def frames_seen(self) -> int:
        return len(self.frames)

    @property
    def in_frame(self) -> bool:
        return self._in_frame

    @property
    def pending_bit_count(self) -> int:
        return self._bit_count


class DescrambledRaw66bParser(Raw66bParser):
    STATE_W = 58
    TAP_1 = 19
    TAP_2 = 0

    def __init__(self):
        super().__init__()
        self._scrambler_state = (1 << self.STATE_W) - 1

    def ingest_66b(self, header: int, payload: int):
        descrambled = self._descramble_payload(payload)
        self._parse_66b(header & 0x3, descrambled)
        self.block_count += 1

    def _descramble_payload(self, payload: int) -> int:
        descrambled = 0
        state = self._scrambler_state
        for bit_idx in range(64):
            scrambled_bit = (payload >> bit_idx) & 1
            feedback = ((state >> self.TAP_1) ^ (state >> self.TAP_2)) & 1
            plain_bit = scrambled_bit ^ feedback
            descrambled |= plain_bit << bit_idx
            state = ((state << 1) | scrambled_bit) & ((1 << self.STATE_W) - 1)
        self._scrambler_state = state
        return descrambled


class TxScoreboard:
    def __init__(self, monitor=None, model=None, checker=None):
        self.monitor = monitor
        self.model = model
        self.checker = checker
        self.expected_frames: list[list[int]] = []
        self.parser = Raw66bParser()
        self.raw_parser = DescrambledRaw66bParser()
        self.raw_chunks_seen = 0
        self.pcs_blocks_seen = 0
        self.match_count = 0
        self.error_count = 0
        self.missing_count = 0
        self.unexpected_count = 0
        self.warnings: list[str] = []

    async def notify(self, notification):
        if isinstance(notification, dict) and "frame" in notification:
            self.add_expected(notification["frame"])
            return
        if isinstance(notification, (list, tuple)):
            self.add_expected(list(notification))
            return
        raise TypeError(f"Unsupported TX scoreboard notification: {notification!r}")

    def add_expected(self, frame: list[int]):
        self.expected_frames.append([b & 0xFF for b in frame])

    @property
    def expected_count(self) -> int:
        return len(self.expected_frames)

    @property
    def actual_count(self) -> int:
        return self.raw_parser.frames_seen

    @property
    def received_expected(self) -> bool:
        if self.expected_count == 0:
            return False
        return not self._missing_expected(self.raw_parser.frames, ordered=False)

    def ingest_raw(self, raw: int):
        self.raw_chunks_seen += 1
        self.raw_parser.ingest_raw64(raw)

    def ingest_pcs(self, header: int, payload: int):
        self.pcs_blocks_seen += 1
        self.parser.ingest_66b(header, payload)

    def check(self, ordered: bool = True):
        self.warnings.clear()
        self.match_count = 0
        self.error_count = 0
        self.missing_count = 0
        self.unexpected_count = 0

        if self.parser.bad_blocks:
            self.error_count += len(self.parser.bad_blocks)
            raise AssertionError(
                "Illegal PCS 66b block(s) observed before scrambler: "
                f"{self.summary()}"
            )

        raw_missing = self._missing_expected(self.raw_parser.frames, ordered=ordered)
        pcs_missing = self._missing_expected(self.parser.frames, ordered=ordered)

        if raw_missing:
            self.missing_count = len(raw_missing)
            self.error_count += self.missing_count
            hint = (
                "PCS output contained the expected payload(s), but final raw "
                "descrambled output did not. Check scrambler/debubbler behavior."
                if not pcs_missing
                else "Expected payload(s) were not observed at PCS or final raw output."
            )
            raise AssertionError(f"{hint} {self.summary()}")

        self.match_count = self.expected_count

        extra_raw = len(self.raw_parser.frames) - self.expected_count
        if extra_raw > 0:
            self.unexpected_count = extra_raw
            self.warnings.append(
                f"Observed {extra_raw} extra decoded raw frame(s); "
                "this test only requires expected payloads to be present."
            )

        if pcs_missing:
            self.warnings.append(
                "Final raw output contained the expected payloads, but the "
                "pre-scrambler PCS monitor did not find all of them."
            )

        if self.raw_parser.bad_blocks:
            self.warnings.append(
                f"Final raw stream had {len(self.raw_parser.bad_blocks)} "
                "unrecognized descrambled 66b block(s)."
            )

        if self.raw_parser.in_frame:
            self.warnings.append(
                "Final raw parser still had a partial frame when checking completed."
            )

    def _missing_expected(self, frames: list[list[int]], ordered: bool) -> list[list[int]]:
        missing: list[list[int]] = []
        used: set[int] = set()
        next_idx = 0

        for expected in self.expected_frames:
            found_idx = None
            search_range = range(next_idx, len(frames)) if ordered else range(len(frames))
            for idx in search_range:
                if not ordered and idx in used:
                    continue
                if self._contains_payload(frames[idx], expected):
                    found_idx = idx
                    break

            if found_idx is None:
                missing.append(expected)
            elif ordered:
                next_idx = found_idx + 1
            else:
                used.add(found_idx)

        return missing

    def summary(self) -> str:
        return (
            "TxScoreboard summary: "
            f"expected={self.expected_count} raw_actual={self.raw_parser.frames_seen} "
            f"pcs_actual={self.parser.frames_seen} passed={self.match_count} "
            f"errors={self.error_count} missing={self.missing_count} "
            f"unexpected={self.unexpected_count} pcs_blocks={self.pcs_blocks_seen} "
            f"raw_chunks={self.raw_chunks_seen} raw_blocks={self.raw_parser.block_count} "
            f"pcs_bad_blocks={len(self.parser.bad_blocks)} "
            f"raw_bad_blocks={len(self.raw_parser.bad_blocks)} "
            f"raw_pending_bits={self.raw_parser.pending_bit_count}"
        )

    @staticmethod
    def _contains_payload(frame: list[int], expected: list[int]) -> bool:
        if not expected:
            return True
        if len(expected) > len(frame):
            return False
        for idx in range(len(frame) - len(expected) + 1):
            if frame[idx : idx + len(expected)] == expected:
                return True
        return False


class Pcs66bChecker:
    LEGAL_CTRL_BLOCKS = {
        Raw66bParser.IDLE_BLK,
        Raw66bParser.SOF_L0,
        Raw66bParser.SOF_L4,
        *Raw66bParser.TERM_TO_VALID.keys(),
    }

    def __init__(self):
        self.blocks_seen = 0
        self.bad_blocks: list[tuple[int, int]] = []
        self.error_count = 0

    def ingest(self, header: int, payload: int):
        self.blocks_seen += 1
        payload_bytes = list(payload.to_bytes(8, "little"))

        if header == Raw66bParser.DATA_HDR:
            return

        if header != Raw66bParser.CTRL_HDR:
            self.bad_blocks.append((header, payload))
            return

        if payload_bytes[0] not in self.LEGAL_CTRL_BLOCKS:
            self.bad_blocks.append((header, payload))

    def check(self):
        self.error_count = len(self.bad_blocks)

    def summary(self) -> str:
        return (
            "Pcs66bChecker summary: "
            f"blocks={self.blocks_seen} bad_blocks={len(self.bad_blocks)} "
            f"errors={self.error_count}"
        )
