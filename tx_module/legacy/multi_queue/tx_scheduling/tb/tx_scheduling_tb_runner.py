import os
from pathlib import Path

from cocotb_tools.runner import get_runner


TB_DIR = Path(__file__).resolve().parent
TX_SCHED_DIR = TB_DIR.parent
TX_MODULE_DIR = TX_SCHED_DIR.parent
REPO_ROOT = TX_MODULE_DIR.parent

SOURCES = [
    str(TX_SCHED_DIR / "rtl" / "tx_scheduling_pkg.sv"),
    str(TX_SCHED_DIR / "rtl" / "tx_scheduling.sv"),
] + sorted(str(p) for p in (REPO_ROOT / "rtl_utils").glob("*.sv"))

SIM_ARGS = [
    "-64",
    "-voptargs=+acc",
]


def _set_pythonpath() -> str:
    path_parts = [str(TX_MODULE_DIR), str(REPO_ROOT), str(TB_DIR)]
    current_pythonpath = os.environ.get("PYTHONPATH")
    if current_pythonpath:
        path_parts.append(current_pythonpath)

    new_pythonpath = os.pathsep.join(path_parts)
    os.environ["PYTHONPATH"] = new_pythonpath
    return new_pythonpath


def _int_list_from_env(name: str, default: str) -> list[int]:
    raw = os.environ.get(name, default)
    vals = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        vals.append(int(tok))

    if not vals:
        vals = [int(tok) for tok in default.split(",") if tok.strip()]

    unique = []
    for v in vals:
        if v not in unique:
            unique.append(v)
    return unique


def test_tx_scheduling():
    pythonpath = _set_pythonpath()

    sim = get_runner("questa")
    queue_configs = _int_list_from_env("TX_SCHED_NUM_QUEUES", "1,2,4,8")
    burst_configs = _int_list_from_env("TX_SCHED_MAX_BURST_BEATS", "256,1")
    waves = os.environ.get("COCOTB_WAVES", "1") != "0"

    for num_queues in queue_configs:
        for max_burst_beats in burst_configs:
            rtl_parameters = {
                "NUM_QUEUES": num_queues,
                "MAX_BURST_BEATS": max_burst_beats,
            }

            sim.build(
                sources=SOURCES,
                hdl_toplevel="tx_scheduling",
                build_dir=str(TX_SCHED_DIR / f"sim_build_q{num_queues}_b{max_burst_beats}"),
                parameters=rtl_parameters,
                always=True,
                clean=True,
            )

            sim.test(
                hdl_toplevel="tx_scheduling",
                test_module="tx_scheduling_test",
                waves=waves,
                test_args=SIM_ARGS,
                extra_env={
                    "TOPLEVEL_LANG": "verilog",
                    "PYTHONPATH": pythonpath,
                    "TX_SCHED_ACTIVE_NUM_QUEUES": str(num_queues),
                    "TX_SCHED_ACTIVE_MAX_BURST_BEATS": str(max_burst_beats),
                },
            )


if __name__ == "__main__":
    test_tx_scheduling()
