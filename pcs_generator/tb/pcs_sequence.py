from random import randint
from typing import Any

from pcs_generator.tb.pcs_sequence_item import PCSSequenceItem
from tb_utils.generic_sequence import GenericSequence


class PCSSequence(GenericSequence[PCSSequenceItem]):
    CHUNK_BYTES = PCSSequenceItem.TKEEP_W
    FULL_TKEEP_MASK = (1 << CHUNK_BYTES) - 1
    MIN_FRAME_BYTES = 64
    DIRTY_PAUSE_INSERT_NUMERATOR = 3
    DIRTY_PAUSE_INSERT_DENOMINATOR = 4

    # Notifies subscribers with the full input transaction so downstream models
    # can reconstruct expected payload bytes and frame boundaries.
    async def add_transaction(self, transaction: PCSSequenceItem):
        await self.notify_subscribers(transaction)
        await super().add_transaction(transaction)

    # Validates manual stream input and converts supported byte-like formats
    # into a normalized bytes object for downstream chunking logic.
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

    # Validates the requested random stream length so both clean and dirty
    # helpers share the same argument checking.
    def _validate_random_stream_length(self, length: int) -> None:
        if not isinstance(length, int):
            raise ValueError(f"length must be an integer, got {type(length).__name__}")
        if length < self.MIN_FRAME_BYTES:
            raise ValueError(
                f"25G Ethernet packets must be at least {self.MIN_FRAME_BYTES} bytes, "
                f"got {length}"
            )

    # Enforces the minimum 25G Ethernet frame size on fully specified stream
    # payloads before any AXI chunking or dirty-pause insertion occurs.
    def _validate_stream_bytes(self, stream_bytes: bytes) -> None:
        if len(stream_bytes) < self.MIN_FRAME_BYTES:
            raise ValueError(
                f"25G Ethernet packets must be at least {self.MIN_FRAME_BYTES} bytes, "
                f"got {len(stream_bytes)}"
            )

    # Generates random stream bytes after validating the requested payload size.
    def _generate_random_stream_bytes(self, length: int) -> bytes:
        self._validate_random_stream_length(length)
        return bytes(randint(0, 0xFF) for _ in range(length))

    # Builds the AXI-S tkeep mask for a chunk based on how many bytes are valid.
    # Rejects values that exceed the configured chunk width.
    def _tkeep_from_num_valid_bytes(self, num_valid_bytes: int) -> int:
        if not 0 <= num_valid_bytes <= self.CHUNK_BYTES:
            raise ValueError(
                f"num_valid_bytes must be between 0 and {self.CHUNK_BYTES}, got {num_valid_bytes}"
            )

        if num_valid_bytes == 0:
            return 0

        return (1 << num_valid_bytes) - 1

    # Packs a byte chunk into an integer with the first byte placed in the least
    # significant byte position, matching the sequence's stream encoding.
    def _pack_chunk_lsb_first(self, chunk: bytes) -> int:
        if len(chunk) > self.CHUNK_BYTES:
            raise ValueError(
                f"chunk length must be <= {self.CHUNK_BYTES} bytes, got {len(chunk)}"
            )

        packed = 0
        for byte_index, byte_value in enumerate(chunk):
            packed |= byte_value << (8 * byte_index)

        return packed

    # Internal helper that forwards keyword arguments to the public AXIS
    # transaction builder so chunk emitters can reuse one call path.
    async def _send_axis_transaction(self, **transaction_kwargs) -> PCSSequenceItem:
        return await self.add_axis_transaction(**transaction_kwargs)

    # Internal helper for stream emitters that always forces idle low so data
    # chunks are never tagged as idle transactions.
    async def _send_non_idle_axis_transaction(
        self, **transaction_kwargs
    ) -> PCSSequenceItem:
        transaction_kwargs["idle"] = 0
        return await self.add_axis_transaction(**transaction_kwargs)

    # Emits a pause cycle for dirty streams by deasserting out_ready without
    # marking the cycle as idle or driving a new valid AXIS beat.
    async def _emit_dirty_pause(self, *, tready: Any = 0) -> PCSSequenceItem:
        return await self._send_non_idle_axis_transaction(
            tdata=0,
            tkeep=0,
            tvalid=0,
            tlast=0,
            out_ready=0,
            tready=tready,
        )

    # Randomly decides whether a dirty stream should insert another pause cycle
    # before attempting to send the next real data chunk.
    def _should_emit_dirty_pause(self) -> bool:
        return (
            randint(1, self.DIRTY_PAUSE_INSERT_DENOMINATOR)
            <= self.DIRTY_PAUSE_INSERT_NUMERATOR
        )

    # Yields each stream chunk together with the AXIS fields needed to emit it
    # as one transaction on the configured bus width.
    def _iter_stream_chunk_transaction_fields(self, stream_bytes: bytes):
        total_len = len(stream_bytes)

        for chunk_start in range(0, total_len, self.CHUNK_BYTES):
            chunk = stream_bytes[chunk_start : chunk_start + self.CHUNK_BYTES]
            yield {
                "tdata": self._pack_chunk_lsb_first(chunk),
                "tkeep": self._tkeep_from_num_valid_bytes(len(chunk)),
                "tvalid": 1,
                "tlast": chunk_start + self.CHUNK_BYTES >= total_len,
            }

    # Emits a normalized byte stream as AXIS transactions, optionally inserting
    # random non-idle pause cycles before each real chunk for dirty streams.
    async def _emit_stream(
        self,
        stream_bytes: bytes,
        *,
        out_ready: Any = 1,
        tready: Any = 0,
        dirty: bool = False,
    ) -> None:
        self._validate_stream_bytes(stream_bytes)

        for transaction_fields in self._iter_stream_chunk_transaction_fields(stream_bytes):
            if dirty:
                while self._should_emit_dirty_pause():
                    await self._emit_dirty_pause(tready=tready)
                chunk_out_ready = 1
            else:
                chunk_out_ready = out_ready

            await self._send_non_idle_axis_transaction(
                **transaction_fields,
                out_ready=chunk_out_ready,
                tready=tready,
            )

    # Creates a PCS sequence item from explicit AXIS signal values, adds it to
    # the sequence, and returns the populated transaction object.
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

    # Creates an arbitrary transaction while forcing the idle flag high, which
    # is useful for injecting explicit idle cycles into the sequence.
    async def add_idle(
        self,
        *,
        tdata: Any = None,
        tkeep: Any = None,
        tvalid: Any = 1,
        tlast: Any = 0,
        out_ready: Any = 1,
        tready: Any = 0,
    ) -> PCSSequenceItem:
        return await self._send_axis_transaction(
            tdata=tdata,
            tkeep=tkeep,
            tvalid=tvalid,
            tlast=tlast,
            out_ready=out_ready,
            tready=tready,
            idle=1,
        )

    # Accepts caller-provided stream data, normalizes it into bytes, and emits
    # the payload as one or more AXIS transactions with idle forced low.
    async def add_manual_stream(
        self, data, *, out_ready: Any = 1, tready: Any = 0
    ) -> None:
        stream_bytes = self._normalize_stream_bytes(data)
        await self._emit_stream(stream_bytes, out_ready=out_ready, tready=tready)

    # Generates a random byte stream of the requested length and sends it out
    # as chunked AXIS transactions with idle forced low after validation.
    async def add_random_stream(
        self, length: int, *, out_ready: Any = 1, tready: Any = 0
    ) -> None:
        stream_bytes = self._generate_random_stream_bytes(length)
        await self._emit_stream(stream_bytes, out_ready=out_ready, tready=tready)

    # Accepts caller-provided stream data and emits it with randomly inserted
    # non-idle pause cycles that deassert out_ready between valid chunks.
    async def add_manual_dirty_stream(self, data, *, tready: Any = 0) -> None:
        stream_bytes = self._normalize_stream_bytes(data)
        await self._emit_stream(stream_bytes, tready=tready, dirty=True)

    # Generates a random byte stream and emits it with randomly inserted
    # non-idle pause cycles before some of the valid chunks.
    async def add_random_dirty_stream(self, length: int, *, tready: Any = 0) -> None:
        stream_bytes = self._generate_random_stream_bytes(length)
        await self._emit_stream(stream_bytes, tready=tready, dirty=True)
