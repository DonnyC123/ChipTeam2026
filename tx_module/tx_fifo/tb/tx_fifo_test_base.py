from tx_fifo.tb.tx_fifo_model import TxFifoModel
from tx_fifo.tb.tx_fifo_sequence import TxFifoSequence
from tx_fifo.tb.tx_fifo_sequence_item import TxFifoSequenceItem
from tx_fifo.tb.tx_fifo_out_transaction import TxFifoOutTransaction

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


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
        super().__init__(
            dut,
            driver,
            sequence_item,
            sequence,
            monitor,
            output_transaction,
            scoreboard,
            model,
            checker,
        )
        self.sequence.add_subscriber(self.scoreboard)
