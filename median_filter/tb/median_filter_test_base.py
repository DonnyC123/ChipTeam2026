from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard

from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem
from median_filter.tb.median_filter_sequence import MedianFilterSequence
from median_filter.tb.median_filter_out_transaction import MedianFilterOutTransaction
from median_filter.tb.median_filter_model import MedianFilterModel


class MedianFilterTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        image_len=4,
        image_height=4,
        driver=GenericDriver,
        sequence_item=MedianFilterSequenceItem,
        sequence=MedianFilterSequence,
        monitor=GenericValidMonitor,
        output_transaction=MedianFilterOutTransaction,
        scoreboard=GenericScoreboard,
        model=None,
        checker=GenericChecker,
    ):
        if model is None:
            model = lambda: MedianFilterModel(image_len=image_len, image_height=image_height)
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
