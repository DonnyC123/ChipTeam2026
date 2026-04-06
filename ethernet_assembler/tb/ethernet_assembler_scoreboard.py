from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_model import GenericModel


class EthernetAssemblerScoreboard:
    def __init__(self, monitor, model=None, checker=None):
        self.monitor = monitor
        self.model = model if model is not None else GenericModel()
        self.checker = checker if checker is not None else GenericChecker()

    async def notify(self, notification):
        await self.model.notify(notification)

    async def check(self):
        await self.checker.check(self.model.expected_queue, self.monitor.actual_queue)

    async def check_with_error_tol(self, error_tol):
        await self.checker.check_with_error_tol(
            self.model.expected_queue, self.monitor.actual_queue, error_tol
        )
