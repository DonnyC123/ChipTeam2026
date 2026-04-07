from tb.tx_subsystem_model import TxSubsystemModel
from tb.tx_subsystem_sequence import TxSubsystemSequence
from tb.tx_subsystem_sequence_item import TxSubsystemSequenceItem
from tb.tx_subsystem_out_transaction import TxSubsystemOutTransaction

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class TxSubsystemTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=TxSubsystemSequenceItem,
        sequence=TxSubsystemSequence,
        monitor=GenericValidMonitor,
        output_transaction=TxSubsystemOutTransaction,
        scoreboard=GenericScoreboard,
        model=TxSubsystemModel,
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
