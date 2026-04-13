from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard
from tb_utils.generic_test_base import GenericTestBase

from tx_pcs_generator_model import TxPcsGeneratorModel
from tx_pcs_generator_out_transaction import TxPcsGeneratorOutTransaction
from tx_pcs_generator_sequence import TxPcsGeneratorSequence
from tx_pcs_generator_sequence_item import TxPcsGeneratorSequenceItem


class TxPcsGeneratorTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=TxPcsGeneratorSequenceItem,
        sequence=TxPcsGeneratorSequence,
        monitor=GenericValidMonitor,
        output_transaction=TxPcsGeneratorOutTransaction,
        scoreboard=GenericScoreboard,
        model=TxPcsGeneratorModel,
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
