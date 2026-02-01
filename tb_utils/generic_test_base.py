from typing import TypeVar, Generic, Type
from cocotb.triggers import RisingEdge, Timer

from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_sequence import GenericSequence
from tb_utils.generic_monitor import GenericMonitor
from tb_utils.generic_scoreboard import GenericScoreboard
from tb_utils.generic_model import GenericModel
from tb_utils.generic_checker import GenericChecker
from tb_utils.abstract_transactions import AbstractTransaction


DriverT = TypeVar("DriverT", bound=GenericDriver)
SequenceT = TypeVar("SequenceT", bound=GenericSequence)
MonitorT = TypeVar("MonitorT", bound=GenericMonitor)
ScoreboardT = TypeVar("ScoreboardT", bound=GenericScoreboard)
ModelT = TypeVar("ModelT", bound=GenericModel)
CheckerT = TypeVar("CheckerT", bound=GenericChecker)
SeqItemT = TypeVar("SeqItemT", bound=AbstractTransaction)
OutTransT = TypeVar("OutTransT", bound=AbstractTransaction)


class GenericTestBase(
    Generic[
        DriverT, SeqItemT, SequenceT, MonitorT, OutTransT, ScoreboardT, ModelT, CheckerT
    ]
):
    def __init__(
        self,
        dut,
        driver: Type[DriverT] = GenericDriver,
        sequence_item: Type[SeqItemT] = AbstractTransaction,
        sequence: Type[SequenceT] = GenericSequence,
        monitor: Type[MonitorT] = GenericMonitor,
        output_transaction: Type[OutTransT] = AbstractTransaction,
        scoreboard: Type[ScoreboardT] = GenericScoreboard,
        model: Type[ModelT] = GenericModel,
        checker: Type[CheckerT] = GenericChecker,
    ):
        self.dut = dut

        self.driver: DriverT = driver(dut=dut, seq_item_type=sequence_item)
        self.sequence: SequenceT = sequence(driver=self.driver)
        self.monitor: MonitorT = monitor(dut=dut, output_transaction=output_transaction)

        self.scoreboard: ScoreboardT = scoreboard(
            monitor=self.monitor, model=model(), checker=checker()
        )

    async def wait_for_driver_done(self):
        while await self.driver.busy():
            await RisingEdge(self.dut.clk)

        await Timer(1000, unit="ns")
