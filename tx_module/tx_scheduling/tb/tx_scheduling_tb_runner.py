import os
import glob
from cocotb_tools.runner import get_runner

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "tx_scheduling/rtl/tx_scheduling_pkg.sv",
    "tx_scheduling/rtl/tx_scheduling.sv",
] + rtl_utils


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
    base_dir = os.getcwd()
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    modelsim_sim_args = [
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
            build_dir=f"tx_scheduling/sim_build_q{num_queues}",
            parameters=rtl_parameters,
            always=True,
            clean=True,
        )

        sim.test(
            hdl_toplevel="tx_scheduling",
            test_module="tx_scheduling.tb.tx_scheduling_test",
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