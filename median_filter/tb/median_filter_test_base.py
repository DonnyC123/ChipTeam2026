from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_level_monitor import GenericLevelMonitor
from tb_utils.generic_scoreboard import GenericScoreboard

from .median_filter_model import MedianFilterModel
from .median_filter_sequence import MedianFilterSequence
from .median_filter_sequence_item import MedianFilterSequenceItem
from .median_filter_out_transaction import MedianFilterOutTransaction
from .median_filter_done_transaction import MedianFilterDoneTransaction


class MedianFilterTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=MedianFilterSequenceItem,
        sequence=MedianFilterSequence,
        monitor=GenericValidMonitor,
        output_transaction=MedianFilterOutTransaction,
        scoreboard=GenericScoreboard,
        model=MedianFilterModel,
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
        self.done_monitor = GenericLevelMonitor(dut, MedianFilterDoneTransaction, True)

        self.sequence.add_subscriber(self.scoreboard)

    async def wait_for_done_monitor(self):
        await self.done_monitor.BlockUntilOneHigh()
