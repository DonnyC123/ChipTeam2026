from tb_utils.generic_model import GenericModel
from tb_utils.generic_checker import GenericChecker


class GenericScoreboard:
    def __init__(self, monitor, model=GenericModel(), checker=GenericChecker()):
        self.monitor = monitor
        self.model = model
        self.checker = checker

    async def notify(self, notification):
        await self.model.notify(notification)

    async def check(self):
        await self.checker.check(self.model.expected_queue, self.monitor.actual_queue)

    async def check_with_error_tol(self, error_tol):
        await self.checker.check_with_error_tol(
            self.model.expected_queue, self.monitor.actual_queue, error_tol
        )
