#!/usr/bin/tcsh -f

set script_dir = `dirname "$0"`
cd "$script_dir"

source /vol/eecs392/env/synplify.env

mkdir -p build

if (! $?TX_SYN_TOP) then
    setenv TX_SYN_TOP tx_top
endif

if (! $?TX_SYN_PART) then
    echo "TX_SYN_PART is unset. Example:"
    echo "  setenv TX_SYN_PART <xilinx_part_number>"
    echo "Running compile-only smoke; timing/device reports will not be meaningful."
endif

synplify_premier -batch -tcl tx_synplify.tcl -log build/synplify.log
