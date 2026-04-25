from tb_utils.generic_model import GenericModel


class TxSubsystemModel(GenericModel):
    PCS_DATA_W = 64
    PCS_VALID_W = 8
    BEATS_PER_WORD = 4

    @classmethod
    def _terminal_beat_idx(cls, keep: int, last: int) -> int:
        if not last:
            return cls.BEATS_PER_WORD - 1

        keep_mask = (1 << cls.PCS_VALID_W) - 1
        terminal = 0
        for beat in range(cls.BEATS_PER_WORD):
            beat_keep = (keep >> (beat * cls.PCS_VALID_W)) & keep_mask
            if beat_keep != 0:
                terminal = beat
        return terminal

    async def process_notification(self, notification):
        data = int(notification.get("data", 0))
        keep = int(notification.get("keep", 0))
        last = int(notification.get("last", 0))

        data_mask = (1 << self.PCS_DATA_W) - 1
        keep_mask = (1 << self.PCS_VALID_W) - 1

        terminal_beat = self._terminal_beat_idx(keep, last)
        for beat in range(terminal_beat + 1):
            beat_data = (data >> (beat * self.PCS_DATA_W)) & data_mask
            beat_keep = (keep >> (beat * self.PCS_VALID_W)) & keep_mask
            beat_last = 1 if (last and beat == terminal_beat) else 0
            await self.expected_queue.put((beat_data, beat_keep, beat_last))
