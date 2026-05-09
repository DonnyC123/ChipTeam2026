#!/usr/bin/tcsh -f

set script_dir = `dirname "$0"`
cd "$script_dir/../.."
set repo_root = `pwd`
set build_dir = "$repo_root/TX/lint/build/questa_lint"

source /vol/eecs392/env/questasim.env

mkdir -p "$build_dir"
cd "$build_dir"

if (-d tx_lint) then
    vdel -lib tx_lint -all
endif

vlib tx_lint

set sources = ( \
    "$repo_root/TX/rtl/tx_fifo/tx_subsystem_pkg.sv" \
    "$repo_root/TX/rtl/tx_fifo/tx_async_fifo.sv" \
    "$repo_root/TX/rtl/tx_fifo/tx_subsystem.sv" \
    "$repo_root/TX/rtl/crc_inserter/crc_inserter.sv" \
    "$repo_root/TX/rtl/pcs_generator/tx_axis_if.sv" \
    "$repo_root/TX/rtl/pcs_generator/pcs_pkg.sv" \
    "$repo_root/TX/rtl/pcs_generator/data_pipeline.sv" \
    "$repo_root/TX/rtl/pcs_generator/pcs_generator.sv" \
    "$repo_root/TX/rtl/scrambler/scrambler.sv" \
    "$repo_root/TX/rtl/debubbler/debubbler.sv" \
    "$repo_root/TX/tb/tx_top.sv" \
)

foreach source_file ($sources)
    echo "Linting $source_file"
    vlog -work tx_lint -sv -lint "$source_file"
    if ($status != 0) then
        echo "Questa lint failed while compiling $source_file"
        exit 1
    endif
end

echo "Questa lint completed successfully."
