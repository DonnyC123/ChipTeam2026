from random import randint
from typing import Any

from pcs_generator.tb.pcs_sequence_item import PCSSequenceItem
from tb_utils.generic_sequence import GenericSequence


class PCSSequence(GenericSequence[PCSSequenceItem]):
    CHUNK_BYTES = PCSSequenceItem.TKEEP_W
    FULL_TKEEP_MASK = (1 << CHUNK_BYTES) - 1

    async def add_transaction(self, transaction: PCSSequenceItem):
        expected_idle = bool(transaction.idle) or not (
            bool(transaction.tvalid) and bool(transaction.out_ready)
        )
        await self.notify_subscribers(expected_idle)
        await super().add_transaction(transaction)

    def _normalize_stream_bytes(self, data: Any) -> bytes:
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)

        if isinstance(data, (list, tuple)):
            normalized = []
            for value in data:
                if not isinstance(value, int) or not 0 <= value <= 0xFF:
                    raise ValueError("manual stream bytes must be integers in the range 0-255")
                normalized.append(value)
            return bytes(normalized)

        raise ValueError(
            "manual stream data must be bytes, bytearray, or a list/tuple of integers"
        )

    def _tkeep_from_num_valid_bytes(self, num_valid_bytes: int) -> int:
        if not 0 <= num_valid_bytes <= self.CHUNK_BYTES:
            raise ValueError(
                f"num_valid_bytes must be between 0 and {self.CHUNK_BYTES}, got {num_valid_bytes}"
            )

        if num_valid_bytes == 0:
            return 0

        return (1 << num_valid_bytes) - 1

    def _pack_chunk_lsb_first(self, chunk: bytes) -> int:
        if len(chunk) > self.CHUNK_BYTES:
            raise ValueError(
                f"chunk length must be <= {self.CHUNK_BYTES} bytes, got {len(chunk)}"
            )

        packed = 0
        for byte_index, byte_value in enumerate(chunk):
            packed |= byte_value << (8 * byte_index)

        return packed

    async def _send_axis_transaction(self, **transaction_kwargs) -> PCSSequenceItem:
        return await self.add_axis_transaction(**transaction_kwargs)

    async def _emit_stream_chunks(
        self, stream_bytes: bytes, *, out_ready: Any = 1, tready: Any = 0
    ) -> None:
        total_len = len(stream_bytes)

        for chunk_start in range(0, total_len, self.CHUNK_BYTES):
            chunk = stream_bytes[chunk_start : chunk_start + self.CHUNK_BYTES]
            await self._send_axis_transaction(
                tdata=self._pack_chunk_lsb_first(chunk),
                tkeep=self._tkeep_from_num_valid_bytes(len(chunk)),
                tvalid=1,
                tlast=chunk_start + self.CHUNK_BYTES >= total_len,
                out_ready=out_ready,
                tready=tready,
                idle=0,
            )

    async def add_axis_transaction(
        self,
        *,
        tdata: Any,
        tkeep: Any,
        tvalid: Any = 1,
        tlast: Any = 0,
        out_ready: Any = 1,
        tready: Any = 0,
        idle: Any = 0,
    ) -> PCSSequenceItem:
        transaction = PCSSequenceItem(idle=idle, tready=tready)
        transaction.tdata = tdata
        transaction.tkeep = tkeep
        transaction.tvalid = tvalid
        transaction.tlast = tlast
        transaction.out_ready = out_ready

        await self.add_transaction(transaction)
        return transaction

    async def add_manual_stream(
        self, data, *, out_ready: Any = 1, tready: Any = 0
    ) -> None:
        stream_bytes = self._normalize_stream_bytes(data)
        await self._emit_stream_chunks(stream_bytes, out_ready=out_ready, tready=tready)

    async def add_random_stream(
        self, length: int, *, out_ready: Any = 1, tready: Any = 0
    ) -> None:
        if not isinstance(length, int):
            raise ValueError(f"length must be an integer, got {type(length).__name__}")
        if length < 0:
            raise ValueError(f"length must be non-negative, got {length}")

        stream_bytes = bytes(randint(0, 0xFF) for _ in range(length))
        await self._emit_stream_chunks(stream_bytes, out_ready=out_ready, tready=tready)
