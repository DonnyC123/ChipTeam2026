import os
from pathlib import Path

from cocotb_tools.runner import get_runner


TB_DIR = Path(__file__).resolve().parent
TX_FIFO_DIR = TB_DIR.parent
TX_MODULE_DIR = TX_FIFO_DIR.parent
REPO_ROOT = TX_MODULE_DIR.parent

SOURCES = [
    str(TX_FIFO_DIR / "rtl" / "tx_fifo_pkg.sv"),
    str(TX_FIFO_DIR / "rtl" / "tx_fifo.sv"),
] + sorted(str(p) for p in (REPO_ROOT / "rtl_utils").glob("*.sv"))

DEPTH = 64
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


def test_tx_fifo():
    pythonpath = _set_pythonpath()

    sim = get_runner("questa")

    rtl_parameters = {
        "DEPTH": DEPTH,
    }

    sim.build(
        sources=SOURCES,
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
        test_args=SIM_ARGS,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": pythonpath,
        },
    )


if __name__ == "__main__":
    test_tx_fifo()
