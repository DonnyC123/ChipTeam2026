import os
from pathlib import Path
from cocotb_tools.runner import get_runner

TB_DIR = Path(__file__).resolve().parent
TX_SCHED_DIR = TB_DIR.parent
TX_MODULE_DIR = TX_SCHED_DIR.parent
REPO_ROOT = TX_MODULE_DIR.parent

sources = [
    str(TX_SCHED_DIR / "rtl" / "tx_scheduling_pkg.sv"),
    str(TX_SCHED_DIR / "rtl" / "tx_scheduling.sv"),
] + sorted(str(p) for p in (TX_MODULE_DIR / "rtl_utils").glob("*.sv"))


def _queue_configs_from_env() -> list[int]:
    raw = os.environ.get("TX_SCHED_NUM_QUEUES", "2,4,8")
    vals = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        vals.append(int(tok))

    if not vals:
        vals = [2, 4, 8]

    # Preserve order while removing duplicates.
    unique = []
    for v in vals:
        if v not in unique:
            unique.append(v)
    return unique


def test_tx_scheduling():
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    path_parts = [str(TX_MODULE_DIR), str(REPO_ROOT), str(TB_DIR)]
    if current_pythonpath:
        path_parts.append(current_pythonpath)
    new_pythonpath = os.pathsep.join(path_parts)
    os.environ["PYTHONPATH"] = new_pythonpath

    sim = get_runner("questa")

    modelsim_sim_args = [
        "-64",
        "-voptargs=+acc",
    ]

    queue_configs = _queue_configs_from_env()
    waves = os.environ.get("COCOTB_WAVES", "1") != "0"

    for num_queues in queue_configs:
        rtl_parameters = {
            "NUM_QUEUES": num_queues,
        }

        sim.build(
            sources=sources,
            hdl_toplevel="tx_scheduling",
            build_dir=str(TX_SCHED_DIR / f"sim_build_q{num_queues}"),
            parameters=rtl_parameters,
            always=True,
            clean=True,
        )

        sim.test(
            hdl_toplevel="tx_scheduling",
            test_module="tx_scheduling_test",
            waves=waves,
            test_args=modelsim_sim_args,
            extra_env={
                "TOPLEVEL_LANG": "verilog",
                "PYTHONPATH": new_pythonpath,
                "TX_SCHED_ACTIVE_NUM_QUEUES": str(num_queues),
            },
        )


if __name__ == "__main__":
    test_tx_scheduling()
