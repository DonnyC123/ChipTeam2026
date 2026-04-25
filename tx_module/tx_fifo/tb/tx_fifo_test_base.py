from functools import partial

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard
from tx_fifo_model import TxFifoModel
from tx_fifo_out_transaction import TxFifoOutTransaction
from tx_fifo_sequence import TxFifoSequence
from tx_fifo_sequence_item import TxFifoSequenceItem


class TxFifoTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=TxFifoSequenceItem,
        sequence=TxFifoSequence,
        monitor=GenericValidMonitor,
        output_transaction=TxFifoOutTransaction,
        scoreboard=GenericScoreboard,
        model=TxFifoModel,
        checker=GenericChecker,
    ):
        depth = 32
        if hasattr(dut, "DEPTH"):
            try:
                depth = int(dut.DEPTH.value)
            except Exception:
                try:
                    depth = int(dut.DEPTH)
                except Exception:
                    depth = 32

        model_factory = partial(model, depth=depth)
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
