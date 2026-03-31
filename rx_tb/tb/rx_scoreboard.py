import cocotb
# from cocotb.log import SimLog
from rx_tb.tb.rx_transaction import RxTransaction

class RxScoreboard:
    def __init__(self, name: str = "RxScoreboard"):
        # self.log            = SimLog(name)
        self.expected_queue: list[list[int]] = []
        self.match_count    = 0
        self.error_count    = 0
        self.bitslip_count  = 0
        self.lock_loss_count= 0

        self._current_frame: list[int] = []
        self._in_frame: bool = False

    def add_expected(self, frame: list[int]):
        self.expected_queue.append(list(frame))

    def ingest(self, txn: RxTransaction):
        if bool(txn.bitslip_o):
            self.bitslip_count += 1

        if self._in_frame and not bool(txn.locked_o):
            self.lock_loss_count += 1

        if not txn.valid:
            if self._in_frame:
                self._close_frame()
            return

        valid_bytes = txn.valid_bytes  
        if not valid_bytes:
            if self._in_frame:
                self._close_frame()
            return

        if not self._in_frame:
            self._in_frame = True
            self._current_frame = []

        self._current_frame.extend(valid_bytes)

    def flush(self):
        if self._in_frame and self._current_frame:
            self._close_frame()

    def _close_frame(self):
        frame = list(self._current_frame)
        self._current_frame = []
        self._in_frame = False
        self._compare(frame)

    def _compare(self, actual: list[int]):
        if not self.expected_queue:
            self.error_count += 1
            return

        expected = self.expected_queue.pop(0)

        if actual == expected:
            self.match_count += 1
        else:
            self.error_count += 1
            if len(actual) == len(expected):
                bad = [i for i,(a,e) in enumerate(zip(actual, expected)) if a != e]
            raise AssertionError("Frame content mismatch — see log above.")

    def check_all_received(self):
        remaining = len(self.expected_queue)
        if remaining:
            raise AssertionError(
                f"{remaining} expected frame(s) never received by DUT."
            )

    def summary(self) -> str:
        return (
            f"Scoreboard summary: "
            f"{self.match_count} passed, {self.error_count} failed, "
            f"{self.bitslip_count} bitslips, {self.lock_loss_count} lock losses"
        )