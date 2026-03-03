from ethernet_assembler.tb.ethernet_assembler_model import EthernetAssemblerModel
from ethernet_assembler.tb.ethernet_assembler_sequence import EthernetAssemblerSequence
from ethernet_assembler.tb.ethernet_assembler_sequence_item import (
    EthernetAssemblerSequenceItem,
)

from ethernet_assembler.tb.ethernet_assembler_out_transaction import (
    EthernetAssemblerTransaction,
)


from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class EthernetAssemblerTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=EthernetAssemblerSequenceItem,
        sequence=EthernetAssemblerSequence,
        monitor=GenericValidMonitor,
        output_transaction=EthernetAssemblerTransaction,
        scoreboard=GenericScoreboard,
        model=EthernetAssemblerModel,
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
