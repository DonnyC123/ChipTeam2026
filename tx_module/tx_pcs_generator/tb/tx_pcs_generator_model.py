from collections import deque

from tb_utils.generic_model import GenericModel


class TxPcsGeneratorModel(GenericModel):
    DATA_W = 64
    KEEP_W = 8
    SKID_DEPTH = 2
    BYTE_BUF_BYTES = 64

    SYNC_DATA = 0b01
    SYNC_CONTROL = 0b10

    BLOCK_IDLE = 0x1E
    BLOCK_START_S0 = 0x78
    BLOCK_TERM_BY_K = {
        0: 0x87,
        1: 0x99,
        2: 0xAA,
        3: 0xB4,
        4: 0xCC,
        5: 0xD2,
        6: 0xE1,
        7: 0xFF,
    }
    CTRL_IDLE_CODE = 0x00

    def __init__(self):
        super().__init__()
        self._skid = deque(maxlen=self.SKID_DEPTH)
        self._byte_q = deque()
        self._in_frame = False
        self._need_t0 = False

    @staticmethod
    def _pack_bytes_le(byte_list):
        data = 0
        for lane, byte in enumerate(byte_list):
            data |= (int(byte) & 0xFF) << (8 * lane)
        return data

    def _keep_lsb_count(self, keep):
        count = 0
        for i in range(self.KEEP_W):
            if (keep >> i) & 1:
                count += 1
            else:
                break
        return count

    def _find_eop_pos(self, max_scan):
        for idx, (_, eop) in enumerate(list(self._byte_q)[:max_scan]):
            if eop:
                return idx
        return None

    def _can_move_from_skid(self):
        return len(self._skid) > 0 and len(self._byte_q) <= (self.BYTE_BUF_BYTES - self.KEEP_W)

    def _in_ready(self):
        return (len(self._skid) < self.SKID_DEPTH) or (
            len(self._skid) == self.SKID_DEPTH and self._can_move_from_skid()
        )

    def _append_word_bytes(self, data, keep, last):
        nbytes = self._keep_lsb_count(keep) if last else self.KEEP_W
        for i in range(nbytes):
            byte = (data >> (8 * i)) & 0xFF
            eop = bool(last and (i == (nbytes - 1)))
            self._byte_q.append((byte, eop))

    def _emit_idle_block(self):
        payload = [self.BLOCK_IDLE] + [self.CTRL_IDLE_CODE] * 7
        return (self._pack_bytes_le(payload), self.SYNC_CONTROL)

    def _emit_next_block(self):
        if not self._in_frame:
            if len(self._byte_q) < 7:
                return self._emit_idle_block()

            first7 = list(self._byte_q)[:7]
            short_eop_pos = None
            for i, (_, eop) in enumerate(first7):
                if eop:
                    short_eop_pos = i
                    break

            if short_eop_pos is not None and short_eop_pos < 6:
                raise AssertionError(
                    "tx_pcs_generator_model: short frame (<7 bytes before S0/T sequence) is unsupported"
                )

            payload = [self.BLOCK_START_S0] + [byte for (byte, _) in first7]
            for _ in range(7):
                self._byte_q.popleft()

            self._in_frame = True
            self._need_t0 = short_eop_pos == 6
            return (self._pack_bytes_le(payload), self.SYNC_CONTROL)

        if self._need_t0:
            self._need_t0 = False
            self._in_frame = False
            payload = [self.BLOCK_TERM_BY_K[0]] + [self.CTRL_IDLE_CODE] * 7
            return (self._pack_bytes_le(payload), self.SYNC_CONTROL)

        eop_pos = self._find_eop_pos(max_scan=min(8, len(self._byte_q)))
        if len(self._byte_q) >= 8 and (eop_pos is None or eop_pos >= 7):
            out_bytes = []
            for _ in range(8):
                byte, _ = self._byte_q.popleft()
                out_bytes.append(byte)
            if eop_pos == 7:
                self._need_t0 = True
            return (self._pack_bytes_le(out_bytes), self.SYNC_DATA)

        if eop_pos is not None and eop_pos <= 6:
            kbytes = eop_pos + 1
            payload = [self.BLOCK_TERM_BY_K[kbytes]]
            for _ in range(kbytes):
                byte, _ = self._byte_q.popleft()
                payload.append(byte)
            while len(payload) < 8:
                payload.append(self.CTRL_IDLE_CODE)
            self._in_frame = False
            self._need_t0 = False
            return (self._pack_bytes_le(payload), self.SYNC_CONTROL)

        return None

    async def process_notification(self, notification):
        in_valid = bool(notification.get("valid", False))
        out_ready = bool(notification.get("out_ready", False))
        in_data = int(notification.get("data", 0)) & ((1 << self.DATA_W) - 1)
        in_keep = int(notification.get("keep", 0)) & ((1 << self.KEEP_W) - 1)
        in_last = bool(notification.get("last", 0))

        in_ready = self._in_ready()
        if in_valid and in_ready:
            self._skid.append((in_data, in_keep, in_last))

        if self._can_move_from_skid():
            data, keep, last = self._skid.popleft()
            self._append_word_bytes(data, keep, last)

        if not out_ready:
            return

        emitted = self._emit_next_block()
        if emitted is not None:
            await self.expected_queue.put(emitted)
