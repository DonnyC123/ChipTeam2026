from functools import partial

from alignment_finder.tb.alignment_finder_model import AlignmentFinderModel
from alignment_finder.tb.alignment_finder_sequence import AlignmentFinderSequence
from alignment_finder.tb.alignment_finder_sequence_item import AlignmentFinderSequenceItem
from alignment_finder.tb.alignment_finder_transaction import AlignmentFinderOutTransaction
from alignment_finder.tb.alignment_finder_bad_input_model import AlignmentFinderBadInputModel

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class AlignmentFinderTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        *,
        data_width: int = 66,
        good_count: int = 32,
        bad_count: int = 8,
        driver=GenericDriver,
        sequence_item=AlignmentFinderSequenceItem,
        sequence=AlignmentFinderSequence,
        monitor=GenericValidMonitor,
        output_transaction=AlignmentFinderOutTransaction,
        scoreboard=GenericScoreboard,
        checker=GenericChecker,
    ):
        model = partial(
            AlignmentFinderBadInputModel,
            data_width=data_width,
            good_count=good_count,
            bad_count=bad_count,
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

        self.sequence.add_subscriber(self.scoreboard)
