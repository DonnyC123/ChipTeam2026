from multiplier_demo.tb.fast_multiplier_model import FastMultiplierModel
from multiplier_demo.tb.fast_multiplier_sequence import FastMultiplierSequence
from multiplier_demo.tb.fast_multiplier_sequence_item import (
    FastMultiplierSequenceItem,
)

from multiplier_demo.tb.fast_multiplier_out_transaction import (
    FastMultiplierOutTransaction,
)


from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class FastMultiplierTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=FastMultiplierSequenceItem,
        sequence=FastMultiplierSequence,
        monitor=GenericValidMonitor,
        output_transaction=FastMultiplierOutTransaction,
        scoreboard=GenericScoreboard,
        model=FastMultiplierModel,
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
