from tb_utils.generic_scoreboard import GenericScoreboard


class RXFifoScoreboard(GenericScoreboard):
    """Scoreboard variant that forwards both monitor queues to the checker."""

    async def check(self):
        await self.checker.check(
            self.model.expected_queue,
            self.monitor.actual_queue,
            self.monitor.cancel_queue,
        )
