import cocotb
from rx_tb.tb.rx_transaction import RxTransaction


class RxScoreboard:
    def __init__(self, name: str = "RxScoreboard"):
        self.name = name

        # expected is now just a list of booleans
        self._expected_drops: list[bool] = []

        # actual captured drops
        self._actual_drops: list[bool] = []

        self.match_count = 0
        self.error_count = 0

    def add_expected(self, drop: bool):
        """Expect whether checksum drop should occur for a frame."""
        self._expected_drops.append(bool(drop))

    def ingest(self, txn: RxTransaction):
        if txn.checksum_drop_o is None:
            return
        self._actual_drops.append(txn.dropped)

    def flush(self):
        self._actual_drops = []

    def check_all_received(self):
        if len(self._actual_drops) == 0:
            raise AssertionError(
                f"[{self.name}] No transactions received from DUT"
            )

        if len(self._actual_drops) != len(self._expected_drops):
            cocotb.log.warning(
                f"[{self.name}] Expected {len(self._expected_drops)} events "
                f"but got {len(self._actual_drops)}"
            )

        mismatches = []

        for i, (exp, act) in enumerate(zip(self._expected_drops, self._actual_drops)):
            if exp == act:
                self.match_count += 1
            else:
                self.error_count += 1
                mismatches.append((i, exp, act))

                cocotb.log.error(
                    f"[{self.name}] Mismatch @ {i}: expected={exp}, actual={act}"
                )

        if mismatches:
            raise AssertionError(
                f"{len(mismatches)} mismatch(es) detected in checksum drop behavior."
            )