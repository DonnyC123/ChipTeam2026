from functools import partial

from tx_scheduling.tb.tx_scheduling_model import TxSchedulingModel
from tx_scheduling.tb.tx_scheduling_sequence import TxSchedulingSequence
from tx_scheduling.tb.tx_scheduling_sequence_item import TxSchedulingSequenceItem
from tx_scheduling.tb.tx_scheduling_out_transaction import TxSchedulingOutTransaction

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class TxSchedulingTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        num_queues=2,
        driver=GenericDriver,
        sequence_item=TxSchedulingSequenceItem,
        sequence=TxSchedulingSequence,
        monitor=GenericValidMonitor,
        output_transaction=TxSchedulingOutTransaction,
        scoreboard=GenericScoreboard,
        model=TxSchedulingModel,
        checker=GenericChecker,
    ):
        model_factory = partial(model, num_queues=num_queues)
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
