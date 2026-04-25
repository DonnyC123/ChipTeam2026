from cocotb.types import Logic, LogicArray

from tb_utils.generic_sequence import GenericSequence
from tx_scheduling_sequence_item import TxSchedulingSequenceItem


def _num_queues() -> int:
    return TxSchedulingSequenceItem.NUM_QUEUES


class TxSchedulingSequence(GenericSequence):

    async def add_beat(
        self,
        q_valid=0,
        q_last=0,
        fifo_full=False,
        fifo_grant=True,
    ):
        """Drive one scheduler cycle and notify model."""
        await self.notify_subscribers(
            {
                "q_valid": q_valid,
                "q_last": q_last,
                "fifo_full": fifo_full,
                "fifo_grant": fifo_grant,
            }
        )
        await self.add_transaction(
            TxSchedulingSequenceItem(
                q_valid_i=LogicArray.from_unsigned(q_valid, _num_queues()),
                q_last_i=LogicArray.from_unsigned(q_last, _num_queues()),
                fifo_full_i=Logic("1" if fifo_full else "0"),
                fifo_grant_i=Logic("1" if fifo_grant else "0"),
            )
        )

    async def add_frame(self, queue_id: int, num_beats: int, other_valid: int = 0):
        """Send a complete frame on the specified queue.

        other_valid is a bitmask of other queues held valid during this frame
        (useful for testing arbitration under contention).
        """
        q_bit = 1 << queue_id
        for i in range(num_beats):
            is_last = i == (num_beats - 1)
            q_valid = q_bit | other_valid
            q_last = q_bit if is_last else 0
            await self.add_beat(q_valid=q_valid, q_last=q_last)

    async def add_frame_q0(self, num_beats: int):
        await self.add_frame(queue_id=0, num_beats=num_beats)

    async def add_frame_q1(self, num_beats: int):
        await self.add_frame(queue_id=1, num_beats=num_beats)

    async def add_simultaneous_frames(self, q0_num: int, q1_num: int):
        """Both queues present data; scheduler serves Q0 first then Q1.

        Assumes scheduler prefers Q0 (last_served=NUM_QUEUES-1 from reset).
        Q0 has q0_num beats, Q1 has q1_num beats.
        Total driven cycles = q0_num + q1_num.
        Q1 stays valid throughout, waiting while Q0 is served.
        """
        total = q0_num + q1_num
        q0_bit = 1 << 0
        q1_bit = 1 << 1
        for i in range(total):
            q0_v = i < q0_num
            q0_l = q0_v and (i == q0_num - 1)
            q1_l = i == (total - 1)

            q_valid = (q0_bit if q0_v else 0) | q1_bit
            q_last = (q0_bit if q0_l else 0) | (q1_bit if q1_l else 0)
            await self.add_beat(q_valid=q_valid, q_last=q_last)
