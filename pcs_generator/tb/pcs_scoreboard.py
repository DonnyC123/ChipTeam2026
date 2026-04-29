from tb_utils.generic_scoreboard import GenericScoreboard


class PCSScoreboard(GenericScoreboard):
    async def check(self):
        await self.checker.check(self.model.expected_queue, self.monitor.actual_queue)
