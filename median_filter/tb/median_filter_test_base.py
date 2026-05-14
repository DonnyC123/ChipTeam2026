from functools import partial

from median_filter.tb.median_filter_model import MedianFilterModel
from median_filter.tb.median_filter_sequence import MedianFilterSequence
from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem
from median_filter.tb.median_filter_out_transaction import MedianFilterOutTransaction

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class MedianFilterTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        *,
        image_w: int,
        image_h: int,
        image_path: str,
        round_half_up: bool = True,
        driver=GenericDriver,
        sequence_item=MedianFilterSequenceItem,
        sequence=MedianFilterSequence,
        monitor=GenericValidMonitor,
        output_transaction=MedianFilterOutTransaction,
        scoreboard=GenericScoreboard,
        checker=GenericChecker,
    ):
        # Build a model factory that GenericTestBase can instantiate
        model = partial(
            MedianFilterModel,
            image_w=image_w,
            image_h=image_h,
            image_path=image_path,
            round_half_up=round_half_up,
        )

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

        # Let scoreboard receive sequence notifications (start/pixel events)
        self.sequence.add_subscriber(self.scoreboard)
