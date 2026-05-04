import pprint

import cocotb
from scrambler.tb.scrambler_transaction import ScramblerTransaction


class ScramblerScoreboard:
    def __init__(self, name: str = "ScramblerScoreboard"):
        self.name = name

        self._expected_payloads: list[list[int]] = []

        self._assembled_bytes: list[int] = []

        self.match_count    = 0
        self.error_count    = 0
        self.bitslip_count  = 0
        self.lock_loss_count = 0

    def add_expected(self, frame: list[int]):
        self._expected_payloads.append(list(frame))

    def ingest(self, txn: ScramblerTransaction):
        if not txn.valid and txn.n_valid == 0:
            return

        self._assembled_bytes.extend(self._extract_bytes(txn))

    def flush(self):
        self._assembled_bytes = []

    def check_all_received(self):
        missing = []

        for idx, expected in enumerate(self._expected_payloads):
            if self._contains(self._assembled_bytes, expected):
                self.match_count += 1
            else:
                self.error_count += 1
                missing.append((idx, expected))

                print(expected) 
                print(self._assembled_bytes)

                cocotb.log.warning(
                    f"[{self.name}] Expected payload #{idx} "
                    f"({len(expected)} bytes starting "
                    f"0x{expected[0]:02X}...) NOT found in DUT output."
                )

        if missing:
            raise AssertionError(
                f"{len(missing)} expected payload(s) not found in DUT output. "
                f"See warnings above."
            )


    @staticmethod
    def _extract_bytes(txn: ScramblerTransaction) -> list[int]:
        raw = list(txn.valid_bytes)

        if hasattr(txn, "n_valid") and txn.n_valid > 0:
            return raw
        else:
            return []

    @staticmethod
    def _contains(haystack: list[int], needle: list[int]) -> bool:
        if not needle:
            return True
        if len(needle) > len(haystack):
            return False

        n = len(needle)
        first = needle[0]

        for i in range(len(haystack) - n + 1):
            if haystack[i] == first and haystack[i : i + n] == needle:
                return True

        return False