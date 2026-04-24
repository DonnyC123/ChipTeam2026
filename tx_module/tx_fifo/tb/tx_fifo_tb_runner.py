import os
from pathlib import Path
from cocotb_tools.runner import get_runner

TB_DIR = Path(__file__).resolve().parent
TX_FIFO_DIR = TB_DIR.parent
TX_MODULE_DIR = TX_FIFO_DIR.parent
REPO_ROOT = TX_MODULE_DIR.parent

sources = [
    str(TX_FIFO_DIR / "rtl" / "tx_fifo_pkg.sv"),
    str(TX_FIFO_DIR / "rtl" / "tx_fifo.sv"),
] + sorted(str(p) for p in (TX_MODULE_DIR / "rtl_utils").glob("*.sv"))

DEPTH = 64


def test_tx_fifo():
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    path_parts = [str(TX_MODULE_DIR), str(REPO_ROOT), str(TB_DIR)]
    if current_pythonpath:
        path_parts.append(current_pythonpath)
    new_pythonpath = os.pathsep.join(path_parts)
    os.environ["PYTHONPATH"] = new_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "DEPTH": DEPTH,
    }

    modelsim_sim_args = [
        "-64",
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="tx_fifo",
        build_dir=str(TX_FIFO_DIR / "sim_build"),
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    sim.test(
        hdl_toplevel="tx_fifo",
        test_module="tx_fifo_test",
        waves=waves,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_tx_fifo()
