# SystemVerilog Formatter Setup

1. Make sure Python 3 is installed and available, check with

```bash
python3 --version
```

2. In VS Code, install the extension `Custom Local Formatters` by `jkillian`.

## VS Code Configuration

Update `.vscode/settings.json` to include the formatter configuration below.

```json
"[systemverilog]": {
  "editor.defaultFormatter": "jkillian.custom-local-formatters",
  "editor.formatOnSave": true
},
"customLocalFormatters.formatters": [
  {
    "command": "python3 PATH_TO_YOUR_FILE -",
    "languages": ["systemverilog"]
  }
]
```

Notes:

- The trailing `-` tells `sv_formatter.py` to read the file contents from standard input, which is how the VS Code formatter extension invokes it.

## How To Use It

1. Reload VS Code after saving `settings.json`.
2. Open a SystemVerilog file such as `pcs_generator/rtl/pcs_generator.sv`.
3. Format with `Shift+Alt+F`, `Format Document`, or just save the file if `formatOnSave` is enabled.
4. If you are on VSCode you can do Ctr + Shift + P then find "Format document with" and choose custom local formatters

## Command-Line Check

You can test the formatter directly from the terminal:

```bash
python3 /home/oys0546/IEEE_2026/ChipTeam2026/scripts/sv_formatter.py pcs_generator/rtl/pcs_generator.sv
```
## What The Script Formats

`sv_formatter.py` aligns:

- assignment operators such as `=` and `<=`
- declaration fields such as type, signedness, width, and initializer