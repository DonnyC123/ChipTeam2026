set script_dir [file dirname [file normalize [info script]]]
set tx_dir [file dirname $script_dir]
set build_dir [file join $script_dir build]
set project_file [file join $build_dir tx_fullchain_syn.prj]

file mkdir $build_dir
cd $build_dir

if {[file exists $project_file]} {
    file delete -force $project_file
}

project -new $project_file
set_option -project_relative_includes 1
set_option -include_path [file normalize $tx_dir]

if {[info exists ::env(TX_SYN_TOP)] && $::env(TX_SYN_TOP) ne ""} {
    set top_module $::env(TX_SYN_TOP)
} else {
    set top_module tx_top
}
set_option -top_module $top_module

if {[info exists ::env(TX_SYN_PART)] && $::env(TX_SYN_PART) ne ""} {
    set_option -technology Xilinx
    set_option -part $::env(TX_SYN_PART)
} else {
    puts "WARNING: TX_SYN_PART is unset. Synplify can compile the project, but timing/device results are not meaningful."
}

set source_list [file join $script_dir tx_fullchain_sources.f]
set fh [open $source_list r]
while {[gets $fh line] >= 0} {
    set line [string trim $line]
    if {$line eq "" || [string match "#*" $line]} {
        continue
    }
    add_file -verilog -vlog_std sysv [file normalize [file join $script_dir $line]]
}
close $fh

project -save
project -run
project -save
