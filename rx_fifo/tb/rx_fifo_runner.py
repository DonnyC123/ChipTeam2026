import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RX_FIFO_ROOT = REPO_ROOT / "rx_fifo"

sources = [
    RX_FIFO_ROOT / "rtl" / "rx_fifo_pkg.sv",
    REPO_ROOT / "rtl_utils" / "if" / "axi_stream_if.sv",
    RX_FIFO_ROOT / "rtl" / "rx_async_fifo.sv",
    RX_FIFO_ROOT / "rtl" / "rx_fifo_ctrl.sv",
]


def _select_simulator() -> str:
    sim_env = os.environ.get("SIM")
    if sim_env:
        return sim_env

    if shutil.which("vsim") is not None:
        return "questa"

    if shutil.which("verilator") is not None:
        return "verilator"

    raise SystemExit(
        "ERROR: No supported simulator found in PATH (expected 'vsim' or 'verilator'). "
        "Set SIM to a supported cocotb runner name if needed."
    )


def test_rx_fifo():
    from cocotb_tools.runner import get_runner

    from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = str(REPO_ROOT) + os.pathsep + current_pythonpath

    sim_name = _select_simulator()
    sim = get_runner(sim_name)

    rtl_parameters = {
        "S_DATA_W": RXFifoSequenceItem.DATA_IN_W,
    }

    sim_test_args = []
    if sim_name == "questa":
        sim_test_args = [
            "-voptargs=+acc",
        ]

    sim.build(
        sources=sources,
        hdl_toplevel="rx_fifo_ctrl",
        build_dir=str(REPO_ROOT / "sim_build" / "rx_fifo"),
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="rx_fifo_ctrl",
        test_module="rx_fifo.tb.rx_fifo_test",
        waves=True,
        test_args=sim_test_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_rx_fifo()
