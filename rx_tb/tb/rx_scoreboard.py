import cocotb
from rx_tb.tb.rx_transaction import RxTransaction


class RxScoreboard:
    def __init__(self, name: str = "RxScoreboard"):
        self.name = name

        self._expected_payloads: list[list[int]] = []
        self._stream_bytes: list[int] = []
        self._current_frame: list[int] = []

        self.match_count     = 0
        self.error_count     = 0
        self.send_count      = 0
        self.drop_count      = 0

    def add_expected(self, frame: list[int]):
        self._expected_payloads.append(list(frame))

    def ingest(self, txn: RxTransaction):
        if txn.valid:
            bytes_ = txn.valid_bytes
            self._stream_bytes.extend(bytes_)
            self._current_frame.extend(bytes_)

        if txn.send:
            self.send_count += 1
            self._current_frame = []

        if txn.drop:
            self.drop_count += 1
            self._current_frame = []

    def check_all_received(self):
        missing = []

        for idx, expected in enumerate(self._expected_payloads):
            if self._contains(self._stream_bytes, expected):
                self.match_count += 1
            else:
                self.error_count += 1
                missing.append((idx, expected))

                print(self._expected_payloads)
                print(self._stream_bytes)

                cocotb.log.error(
                    f"[{self.name}] Expected payload #{idx} "
                    f"({len(expected)} bytes starting "
                    f"0x{expected[0]:02X}...) NOT found in stream."
                )

        if self.send_count < len(self._expected_payloads):
            self.error_count += 1
            cocotb.log.error(
                f"[{self.name}] CRC FAIL: only {self.send_count} frames passed, "
                f"expected {len(self._expected_payloads)}"
            )

        if self.drop_count > 0:
            cocotb.log.warning(
                f"[{self.name}] {self.drop_count} frame(s) dropped by CRC"
            )

        if missing or self.send_count < len(self._expected_payloads):
            raise AssertionError(
                f"{len(missing)} payload(s) missing, "
                f"{self.send_count}/{len(self._expected_payloads)} frames passed CRC"
            )

    def flush(self):
        self._current_frame = []

    @staticmethod
    def _contains(haystack: list[int], needle: list[int]) -> bool:
        if not needle:
            return True
        if len(needle) > len(haystack):
            return False

        n = len(needle)
        first = needle[0]

        for i in range(len(haystack) - n + 1):
            if haystack[i] == first and haystack[i:i+n] == needle:
                return True

        return False