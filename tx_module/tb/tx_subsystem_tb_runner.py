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

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    cfgs = [
        {
            "name": "axis",
            "mode": "axis",
            "parameters": {
                "USE_DMA_AXIS_INPUT": 1,
                "DMA_RSP_LATENCY": 0,
                "MAX_BURST_BEATS": 256,
            },
        },
        {
            "name": "legacy",
            "mode": "legacy",
            "parameters": {
                "USE_DMA_AXIS_INPUT": 0,
                "DMA_RSP_LATENCY": 0,
                "MAX_BURST_BEATS": 8,
            },
        },
    ]

    for cfg in cfgs:
        sim.build(
            sources=sources,
            hdl_toplevel="tx_subsystem_tb_top",
            build_dir=str(TX_MODULE_DIR / f"sim_build_subsystem_{cfg['name']}"),
            parameters=cfg["parameters"],
            always=True,
            clean=True,
        )

        sim.test(
            hdl_toplevel="tx_subsystem_tb_top",
            test_module="tb.tx_subsystem_test",
            waves=waves,
            test_args=modelsim_sim_args,
            extra_env={
                "TOPLEVEL_LANG": "verilog",
                "PYTHONPATH": new_pythonpath,
                "TX_SUBSYSTEM_INPUT_MODE": cfg["mode"],
                "TX_SUBSYSTEM_MAX_BURST_BEATS": str(cfg["parameters"]["MAX_BURST_BEATS"]),
            },
        )


if __name__ == "__main__":
    test_tx_subsystem()
