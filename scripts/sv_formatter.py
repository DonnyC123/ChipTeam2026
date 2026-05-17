#!/usr/bin/env python3
"""
SystemVerilog Formatter
-----------------------
Aligns '=' signs and declarations within begin...end blocks.
Non-assignment lines (if, case, etc.) break alignment groups.

Usage:
    python sv_formatter.py input.sv            # prints to stdout
    python sv_formatter.py input.sv --inplace  # overwrites the file
"""

import re
import sys


# ── Regex patterns ────────────────────────────────────────────────────────────

# Matches an assignment line:  <lhs> = <rhs>;
# LHS can be: identifier, identifier[bits], identifier.field, etc.
ASSIGN_RE = re.compile(r'^(\s*)([\w\[\].:\'`\s]+?)\s*(<=|=)\s*(.+)$')

# Matches a variable/parameter declaration with optional assignment:
#   logic [7:0]   my_var = 8'hFF;
#   parameter int MY_PARAM = 10;
DECL_RE = re.compile(
    r'^(\s*)((?:logic|wire|reg|input|output|inout|parameter|localparam|int|integer|bit|byte|shortint|longint|real|realtime|time|string)\b.*?)\s*((?<![<>=!])=(?!=))\s*(.+)$'
)

# Lines that break alignment groups (non-assignment control flow)
BREAK_RE = re.compile(r'^\s*(if|else|for|while|case|casez|casex|endcase|always|initial|forever|repeat|fork|join)\b')

# begin / end detection
BEGIN_RE = re.compile(r'\bbegin\b')
END_RE   = re.compile(r'^\s*end\b')

# Declaration helpers
DECL_START_TOKENS = {
    'logic', 'wire', 'reg', 'bit', 'byte', 'shortint', 'int', 'longint',
    'integer', 'time', 'real', 'realtime', 'string', 'input', 'output',
    'inout', 'var', 'const', 'static', 'automatic', 'rand', 'randc'
}

DECL_KIND_CONT_TOKENS = {
    'logic', 'wire', 'reg', 'bit', 'byte', 'shortint', 'int', 'longint',
    'integer', 'time', 'real', 'realtime', 'string', 'input', 'output',
    'inout', 'var', 'const', 'static', 'automatic', 'rand', 'randc'
}

SIGNED_TOKENS = {'signed', 'unsigned'}
PORT_DIR_TOKENS = {'input', 'output', 'inout'}

IDENT_RE = re.compile(r'[A-Za-z_]\w*')


# ── Core alignment logic ──────────────────────────────────────────────────────

def align_group(group):
    """
    Given a list of (indent, lhs, op, rhs) tuples,
    pad each LHS so all '=' signs are in the same column.
    Returns a list of formatted strings.
    """
    if not group:
        return []

    max_lhs = max(len(lhs) for _, lhs, _, _ in group)

    result = []
    for indent, lhs, op, rhs in group:
        padding = ' ' * (max_lhs - len(lhs))
        result.append(f"{indent}{lhs}{padding} {op} {rhs}")
    return result


def flush_group(group, output):
    """Align and emit a pending group into output."""
    output.extend(align_group(group))
    group.clear()


def split_inline_comment(line):
    """
    Split line into (code, comment) at the first // comment marker.
    If no comment exists, comment is ''.
    """
    if '//' not in line:
        return line, ''

    code, comment = line.split('//', 1)
    return code.rstrip(), f"//{comment.strip()}"


def parse_bracket_expr(text, start_idx):
    """
    Parse a balanced [ ... ] expression starting at start_idx.
    Returns (expr, next_idx) or (None, start_idx) on failure.
    """
    if start_idx >= len(text) or text[start_idx] != '[':
        return None, start_idx

    depth = 0
    i = start_idx
    while i < len(text):
        ch = text[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return text[start_idx:i + 1], i + 1
        i += 1

    return None, start_idx


def split_top_level_assignment(text):
    """
    Split declaration tail into (declarators, op, rhs) on a top-level '='.
    The split ignores '=' inside (), [], and {} and ignores comparison ops.
    """
    depth_paren = 0
    depth_brack = 0
    depth_brace = 0

    for i, ch in enumerate(text):
        if ch == '(':
            depth_paren += 1
            continue
        if ch == ')':
            depth_paren = max(0, depth_paren - 1)
            continue
        if ch == '[':
            depth_brack += 1
            continue
        if ch == ']':
            depth_brack = max(0, depth_brack - 1)
            continue
        if ch == '{':
            depth_brace += 1
            continue
        if ch == '}':
            depth_brace = max(0, depth_brace - 1)
            continue

        if ch != '=':
            continue
        if depth_paren or depth_brack or depth_brace:
            continue

        prev_ch = text[i - 1] if i > 0 else ''
        next_ch = text[i + 1] if i + 1 < len(text) else ''
        if prev_ch in '<>!-' or next_ch == '=':
            continue

        declarators = text[:i].rstrip()
        rhs = text[i + 1:].strip()
        if not declarators or not rhs:
            return None, None, None
        return declarators, '=', rhs

    declarators = text.strip()
    if not declarators:
        return None, None, None
    return declarators, '', ''


def split_top_level_commas(text):
    """
    Split text by commas at top level (outside (), [], {}).
    """
    parts = []
    start = 0
    depth_paren = 0
    depth_brack = 0
    depth_brace = 0

    for i, ch in enumerate(text):
        if ch == '(':
            depth_paren += 1
            continue
        if ch == ')':
            depth_paren = max(0, depth_paren - 1)
            continue
        if ch == '[':
            depth_brack += 1
            continue
        if ch == ']':
            depth_brack = max(0, depth_brack - 1)
            continue
        if ch == '{':
            depth_brace += 1
            continue
        if ch == '}':
            depth_brace = max(0, depth_brace - 1)
            continue

        if ch == ',' and not (depth_paren or depth_brack or depth_brace):
            parts.append(text[start:i].strip())
            start = i + 1

    parts.append(text[start:].strip())
    return parts


def try_match_decl_segments(line):
    """
    Try to parse a declaration line into alignment segments:
    (
        indent,
        port_direction,
        kind,
        signedness,
        width,
        declarators,
        op,
        rhs,
        terminator,
        comment,
    )
    Returns None when line doesn't match the declaration format.
    """
    code, comment = split_inline_comment(line)

    stripped_code = code.strip()
    if not stripped_code:
        return None

    terminator = ''
    trim_len = 0
    if stripped_code.endswith(');'):
        terminator = ');'
        trim_len = 2
    elif stripped_code[-1] in (';', ',', ')'):
        terminator = stripped_code[-1]
        trim_len = 1

    if trim_len > 0:
        code_no_terminator = code.rstrip()[:-trim_len].rstrip()
    else:
        code_no_terminator = code.rstrip()
    if not code_no_terminator:
        return None

    indent_match = re.match(r'^(\s*)(.*)$', code_no_terminator)
    indent = indent_match.group(1)
    content = indent_match.group(2).strip()
    if not content:
        return None

    first = IDENT_RE.match(content)
    if not first:
        return None

    if first.group(0) not in DECL_START_TOKENS:
        return None

    # Unterminated declaration lines are only supported for final module ports:
    #     output logic done_out
    #     );
    if terminator == '' and first.group(0) not in PORT_DIR_TOKENS:
        return None
    if terminator in (')', ');') and first.group(0) not in PORT_DIR_TOKENS:
        return None

    i = 0
    n = len(content)

    def skip_ws(idx):
        while idx < n and content[idx].isspace():
            idx += 1
        return idx

    kind_tokens = []
    signedness = ''

    while True:
        i = skip_ws(i)
        if i >= n:
            break
        if content[i] == '[':
            break

        token_match = IDENT_RE.match(content, i)
        if not token_match:
            break

        token = token_match.group(0)
        token_start = token_match.start()
        token_end = token_match.end()

        if token in SIGNED_TOKENS:
            signedness = token
            i = token_end
            break

        if not kind_tokens:
            kind_tokens.append(token)
            i = token_end
            continue

        if token in DECL_KIND_CONT_TOKENS:
            kind_tokens.append(token)
            i = token_end
            continue

        # Reached signal name token.
        i = token_start
        break

    if not kind_tokens:
        return None

    i = skip_ws(i)
    if not signedness:
        token_match = IDENT_RE.match(content, i)
        if token_match and token_match.group(0) in SIGNED_TOKENS:
            signedness = token_match.group(0)
            i = token_match.end()

    i = skip_ws(i)
    width = ''
    if i < n and content[i] == '[':
        width, i = parse_bracket_expr(content, i)
        if width is None:
            return None

    i = skip_ws(i)
    if i >= n:
        return None

    declarators, op, rhs = split_top_level_assignment(content[i:].strip())
    if declarators is None:
        return None

    declarator_parts = split_top_level_commas(declarators)
    if not declarator_parts or any(not part for part in declarator_parts):
        return None
    if any(not IDENT_RE.match(part) for part in declarator_parts):
        return None

    port_direction = ''
    kind_tokens_no_dir = kind_tokens
    if kind_tokens[0] in PORT_DIR_TOKENS:
        port_direction = kind_tokens[0]
        kind_tokens_no_dir = kind_tokens[1:]

    return (
        indent,
        port_direction,
        ' '.join(kind_tokens_no_dir),
        signedness,
        width,
        declarators,
        op,
        rhs,
        terminator,
        comment,
    )


def align_decl_group(group):
    """
    Align declaration groups so kind/signedness/width/name fields are columnized.
    """
    if not group:
        return []

    group_indent = group[0][0]

    max_dir = max(len(port_direction) for _, port_direction, _, _, _, _, _, _, _, _ in group)
    max_kind = max(len(kind) for _, _, kind, _, _, _, _, _, _, _ in group)
    max_signed = max(len(signedness) for _, _, _, signedness, _, _, _, _, _, _ in group)
    max_width = max(len(width) for _, _, _, _, width, _, _, _, _, _ in group)
    max_decl = max(len(declarators) for _, _, _, _, _, declarators, _, _, _, _ in group)
    has_direction = any(port_direction for _, port_direction, _, _, _, _, _, _, _, _ in group)
    has_assignment = any(op for _, _, _, _, _, _, op, _, _, _ in group)

    result = []
    for _, port_direction, kind, signedness, width, declarators, op, rhs, terminator, comment in group:
        line = group_indent
        if has_direction:
            line += port_direction.ljust(max_dir)
            if max_kind > 0:
                line += f" {kind.ljust(max_kind)}"
        else:
            line += kind.ljust(max_kind)
        if max_signed > 0:
            line += f" {signedness.ljust(max_signed)}"
        if max_width > 0:
            line += f" {width.ljust(max_width)}"
        line += f" {declarators}"
        if has_assignment and op:
            line += ' ' * (max_decl - len(declarators))
            line += f" {op} {rhs}"
        line += terminator
        if comment:
            line += f" {comment}"
        result.append(line)

    return result


def flush_decl_group(group, output):
    """Align and emit a pending declaration group into output."""
    output.extend(align_decl_group(group))
    group.clear()


def try_match_assignment(line):
    """
    Try to match line as a plain assignment first, then as a
    declaration-with-assignment. Returns (indent, lhs, op, rhs) or None.
    """
    m = ASSIGN_RE.match(line)
    if m:
        return m.group(1), m.group(2).rstrip(), m.group(3), m.group(4)
    m = DECL_RE.match(line)
    if m:
        return m.group(1), m.group(2).rstrip(), m.group(3), m.group(4)
    return None


# ── Main formatter ────────────────────────────────────────────────────────────

def format_sv(source: str) -> str:
    lines  = source.splitlines(keepends=True)
    output = []
    group  = []        # pending assignment group: list of (indent, lhs, op, rhs)
    decl_group = []    # pending declaration group

    for raw_line in lines:
        line = raw_line.rstrip('\n').rstrip('\r')

        # ── Does this line open a new begin block? ──────────────────────────
        # Flush before entering a nested block so the outer group doesn't
        # accidentally absorb lines from inside the block.
        if BEGIN_RE.search(line):
            flush_decl_group(decl_group, output)
            flush_group(group, output)
            output.append(line)
            continue

        # ── Does this line close a block? ───────────────────────────────────
        if END_RE.match(line):
            flush_decl_group(decl_group, output)
            flush_group(group, output)
            output.append(line)
            continue

        # ── Is it a control-flow line that breaks a group? ──────────────────
        if BREAK_RE.match(line):
            flush_decl_group(decl_group, output)
            flush_group(group, output)
            output.append(line)
            continue

        # ── Is it a blank line? (also breaks groups) ────────────────────────
        if line.strip() == '':
            flush_decl_group(decl_group, output)
            flush_group(group, output)
            output.append(line)
            continue

        # ── Try to match declaration segments ───────────────────────────────
        decl_match = try_match_decl_segments(line)
        if decl_match:
            flush_group(group, output)
            # Keep declaration alignment scoped to one indentation level.
            if decl_group and decl_group[0][0] != decl_match[0]:
                flush_decl_group(decl_group, output)
            decl_group.append(decl_match)
            continue

        # ── Try to match as an assignment ───────────────────────────────────
        match = try_match_assignment(line)
        if match:
            flush_decl_group(decl_group, output)
            group.append(match)
            continue

        # ── Anything else: flush group and pass through ─────────────────────
        flush_decl_group(decl_group, output)
        flush_group(group, output)
        output.append(line)

    # Flush any remaining group at end of file
    flush_decl_group(decl_group, output)
    flush_group(group, output)

    return '\n'.join(output)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Handle stdin mode for VS Code formatter integration
    if len(sys.argv) == 1 or sys.argv[1] == '-':
        source = sys.stdin.read()
        print(format_sv(source), end='')
        return

    filepath = sys.argv[1]
    inplace  = '--inplace' in sys.argv

    with open(filepath, 'r') as f:
        source = f.read()

    formatted = format_sv(source)

    if inplace:
        with open(filepath, 'w') as f:
            f.write(formatted)
        print(f"Formatted: {filepath}", file=sys.stderr)
    else:
        print(formatted)


if __name__ == '__main__':
    main()
