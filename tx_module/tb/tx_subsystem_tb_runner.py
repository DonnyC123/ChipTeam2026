import os
from pathlib import Path

from cocotb_tools.runner import get_runner


TB_DIR = Path(__file__).resolve().parent
TX_MODULE_DIR = TB_DIR.parent
REPO_ROOT = TX_MODULE_DIR.parent

sources = [
    str(TX_MODULE_DIR / "tx_fifo" / "rtl" / "tx_fifo_pkg.sv"),
    str(TX_MODULE_DIR / "tx_fifo" / "rtl" / "tx_fifo.sv"),
    str(TX_MODULE_DIR / "tx_scheduling" / "rtl" / "tx_scheduling_pkg.sv"),
    str(TX_MODULE_DIR / "tx_scheduling" / "rtl" / "tx_scheduling.sv"),
    str(TX_MODULE_DIR / "rtl" / "tx_subsystem.sv"),
    str(TB_DIR / "tx_subsystem_tb_top.sv"),
]


def test_tx_subsystem():
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

    sim.build(
        sources=sources,
        hdl_toplevel="tx_subsystem_tb_top",
        build_dir=str(TX_MODULE_DIR / "sim_build_subsystem"),
        always=True,
        clean=True,
    )

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    sim.test(
        hdl_toplevel="tx_subsystem_tb_top",
        test_module="tb.tx_subsystem_test",
        waves=waves,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_tx_subsystem()
