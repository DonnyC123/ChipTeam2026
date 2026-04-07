from functools import partial

from cocotb.triggers import FallingEdge, ReadOnly

from tx_scheduling.tb.tx_scheduling_model import TxSchedulingModel
from tx_scheduling.tb.tx_scheduling_sequence import TxSchedulingSequence
from tx_scheduling.tb.tx_scheduling_sequence_item import TxSchedulingSequenceItem
from tx_scheduling.tb.tx_scheduling_out_transaction import TxSchedulingOutTransaction

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_scoreboard import GenericScoreboard


class TxSchedulingDriver(GenericDriver):
    """Drive inputs on falling edge so DUT sees stable values at next rising edge."""

    async def driver_loop(self):
        # Force benign defaults before the first sampled clock edge.
        await self.drive_transaction(self.seq_item_type.invalid_seq_item())

        while True:
            await FallingEdge(self.dut.clk)

            if not self.seq_item_queue.empty():
                seq_item = await self.seq_item_queue.get()
            else:
                seq_item = self.seq_item_type.invalid_seq_item()

            await self.drive_transaction(seq_item)


class TxSchedulingMonitor(GenericValidMonitor):
    """Sample combinational scheduler outputs on falling edge.

    The DUT updates internal state on rising edge and drives outputs
    combinationally. Sampling on falling edge captures the stable values
    associated with the in-flight cycle, avoiding post-edge next-cycle values.
    """

    async def receive_transaction(self):
        while True:
            await FallingEdge(self.dut.clk)
            await ReadOnly()

            output_transaction = self.output_transaction()
            await self.recursive_receive(self.dut, output_transaction)

            if output_transaction.valid:
                return output_transaction


class TxSchedulingTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        num_queues=None,
        max_burst_beats=None,
        driver=TxSchedulingDriver,
        sequence_item=TxSchedulingSequenceItem,
        sequence=TxSchedulingSequence,
        monitor=TxSchedulingMonitor,
        output_transaction=TxSchedulingOutTransaction,
        scoreboard=GenericScoreboard,
        model=TxSchedulingModel,
        checker=GenericChecker,
    ):
        if num_queues is None:
            num_queues = len(dut.q_valid_i)
        if max_burst_beats is None:
            max_burst_beats = _read_param_or_default(dut, "MAX_BURST_BEATS", 256)

        qid_w = max(1, (num_queues - 1).bit_length())
        sequence_item.NUM_QUEUES = num_queues
        sequence_item.QID_W = qid_w
        output_transaction.QID_W = qid_w

        model_factory = partial(
            model,
            num_queues=num_queues,
            max_burst_beats=max_burst_beats,
        )
        super().__init__(
            dut,
            driver,
            sequence_item,
            sequence,
            monitor,
            output_transaction,
            scoreboard,
            model_factory,
            checker,
        )
        self.sequence.add_subscriber(self.scoreboard)


def _read_param_or_default(dut, name: str, default: int) -> int:
    """Read a Verilog parameter from DUT if visible in sim; else return default."""
    try:
        obj = getattr(dut, name)
    except AttributeError:
        return default

    for attr in ("value",):
        try:
            val = getattr(obj, attr)
            if hasattr(val, "to_unsigned"):
                return int(val.to_unsigned())
            return int(val)
        except (AttributeError, TypeError, ValueError):
            continue

    try:
        return int(obj)
    except (TypeError, ValueError):
        return default
