import os
from pathlib import Path

from cocotb_tools.runner import get_runner


TB_DIR = Path(__file__).resolve().parent
TX_MODULE_DIR = TB_DIR.parent
REPO_ROOT = TX_MODULE_DIR.parent

SOURCES = [
    str(TX_MODULE_DIR / "tx_fifo" / "rtl" / "tx_fifo_pkg.sv"),
    str(TX_MODULE_DIR / "rtl" / "tx_async_fifo.sv"),
    str(TX_MODULE_DIR / "rtl" / "tx_subsystem.sv"),
    str(TX_MODULE_DIR / "rtl" / "tx_subsystem_axis_1q.sv"),
    str(TB_DIR / "tx_subsystem_tb_top.sv"),
]

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


def test_tx_subsystem():
    pythonpath = _set_pythonpath()
    sim = get_runner("questa")

    rtl_parameters = {
        "FIFO_DEPTH": int(os.environ.get("TX_SUBSYSTEM_FIFO_DEPTH", "16")),
        "DESC_DEPTH": int(os.environ.get("TX_SUBSYSTEM_DESC_DEPTH", "16")),
    }

    sim.build(
        sources=SOURCES,
        hdl_toplevel="tx_subsystem_tb_top",
        build_dir=str(TX_MODULE_DIR / "sim_build_subsystem_axis_1q"),
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"

    sim.test(
        hdl_toplevel="tx_subsystem_tb_top",
        test_module="tx_subsystem_test",
        waves=waves,
        test_args=SIM_ARGS,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": pythonpath,
            "TX_SUBSYSTEM_FIFO_DEPTH": str(rtl_parameters["FIFO_DEPTH"]),
            "TX_SUBSYSTEM_DESC_DEPTH": str(rtl_parameters["DESC_DEPTH"]),
        },
    )


if __name__ == "__main__":
    test_tx_subsystem()
