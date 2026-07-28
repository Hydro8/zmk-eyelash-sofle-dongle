#!/usr/bin/env python3
"""
parse_keymap.py — Parse ZMK zephyr.dts.pre to extract keymap as JSON.

Usage:
    python3 parse_keymap.py <path/to/zephyr.dts.pre> [-o output.json]
"""

import json
import re
import sys
from pathlib import Path

HID_KEY_NAMES = {
    0x00: "NoEvent", 0x01: "OverrunError", 0x02: "POSTFail", 0x03: "POSTErrorUndefined",
    0x04: "aA", 0x05: "bB", 0x06: "cC", 0x07: "dD", 0x08: "eE", 0x09: "fF",
    0x0A: "gG", 0x0B: "hH", 0x0C: "iI", 0x0D: "jJ", 0x0E: "kK", 0x0F: "lL",
    0x10: "mM", 0x11: "nN", 0x12: "oO", 0x13: "pP", 0x14: "qQ", 0x15: "rR",
    0x16: "sS", 0x17: "tT", 0x18: "uU", 0x19: "vV", 0x1A: "wW", 0x1B: "xX",
    0x1C: "yY", 0x1D: "zZ",
    0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5",
    0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab",
    0x2C: "Space", 0x2D: "Minus", 0x2E: "Equal", 0x2F: "BracketLeft",
    0x30: "BracketRight", 0x31: "Backslash",
    0x33: "Semicolon", 0x34: "Quote", 0x35: "Backquote",
    0x36: "Comma", 0x37: "Period", 0x38: "Slash", 0x39: "CapsLock",
    0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4",
    0x3E: "F5", 0x3F: "F6", 0x40: "F7", 0x41: "F8",
    0x42: "F9", 0x43: "F10", 0x44: "F11", 0x45: "F12",
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PageUp",
    0x4C: "Delete", 0x4D: "End", 0x4E: "PageDown",
    0x4F: "RightArrow", 0x50: "LeftArrow", 0x51: "DownArrow", 0x52: "UpArrow",
    0x64: "IntlBackslash",
    0xE0: "LeftShift", 0xE1: "LeftCtrl", 0xE2: "LeftAlt",
    0xE3: "RightShift", 0xE5: "RightAlt", 0xE6: "RightGui",
}

HID_CONSUMER_NAMES = {
    0xB5: "ScanNextTrack", 0xB6: "ScanPrevTrack",
    0xE9: "VolumeUp", 0xEA: "VolumeDown",
    0xE2: "Mute", 0xCD: "PlayPause",
    0x19E: "Record", 0x6F: "Rewind", 0x70: "FastForward",
}

ZMK_BEHAVIOR_OPCODES = {
    0xE0: "LeftShift", 0xE1: "LeftCtrl", 0xE2: "LeftAlt",
    0xE3: "RightShift", 0xE5: "RightAlt", 0xE6: "RightGui",
}

MOD_NAMES = {
    0x04: "LeftCtrl", 0x07: "RightGui", 0x08: "LeftGui",
    0x09: "RightCtrl", 0x0A: "LeftShift", 0x0B: "RightShift",
    0x0C: "LeftAlt", 0x0D: "RightAlt",
}


def _parse_int(s):
    s = s.strip().strip("(").strip(")")
    try:
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16)
        return int(s)
    except (ValueError, OverflowError):
        return None


def _resolve_expression(expr):
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        matched = True
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i < len(expr) - 1:
                    matched = False
                    break
        if matched and depth == 0:
            expr = expr[1:-1].strip()
        else:
            break
    try:
        if expr.startswith("0x") or expr.startswith("0X"):
            int(expr, 16)
        else:
            int(expr)
        return expr
    except ValueError:
        pass
    try:
        if re.match(r'^[\d\sxXabcdefABCDEF+\-|&~()<>()]+$', expr):
            result = eval(expr)
            return hex(result)
    except Exception:
        pass
    return None


def extract_numeric_values(s):
    values = []
    s = s.strip()
    tokens = []
    current = ""
    depth = 0
    for ch in s:
        if ch in " \t\n" and depth == 0:
            if current:
                tokens.append(current)
                current = ""
        else:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            current += ch
    if current:
        tokens.append(current)
    for token in tokens:
        val = _resolve_expression(token.strip())
        if val is not None:
            values.append(val)
        elif token.strip().isdigit():
            values.append(token.strip())
    return values


def decode_value(raw_hex):
    s = raw_hex.strip()
    val = _parse_int(s)
    if val is None:
        return {"type": "unknown", "raw": s}
    usage_page = (val >> 16) & 0xFFFF
    usage_id = val & 0xFFFF
    modifier_prefix = (val >> 24) & 0xFF
    modifiers = []
    key_name = None
    behavior_type = None
    if modifier_prefix == 0x02 and usage_page == 0x07:
        modifiers.append("LeftShift")
        key_name = HID_KEY_NAMES.get(usage_id, "Unknown_{:02X}".format(usage_id))
        behavior_type = "kp"
    elif modifier_prefix == 0x08:
        mod_name = MOD_NAMES.get(usage_id, "Mod_{:02X}".format(usage_id))
        modifiers.append(mod_name)
        behavior_type = "mod"
        key_name = mod_name
    elif modifier_prefix == 0x20:
        modifiers.append("LeftGui")
        key_name = HID_KEY_NAMES.get(usage_id, "Unknown_{:02X}".format(usage_id))
        behavior_type = "kp"
    elif modifier_prefix == 0x40:
        modifiers.append("LeftCtrl")
        key_name = HID_KEY_NAMES.get(usage_id, "Unknown_{:02X}".format(usage_id))
        behavior_type = "kp"
    elif usage_page == 0x07:
        key_name = HID_KEY_NAMES.get(usage_id, "HID_{:02X}".format(usage_id))
        behavior_type = "kp"
    elif usage_page == 0x0C:
        key_name = HID_CONSUMER_NAMES.get(usage_id, "Consumer_{:02X}".format(usage_id))
        behavior_type = "kp"
    elif usage_page == 0x0E:
        key_name = ZMK_BEHAVIOR_OPCODES.get(usage_id, "Behavior_{:02X}".format(usage_id))
        behavior_type = "mod"
    if behavior_type:
        result = {"type": behavior_type}
        if key_name:
            result["key"] = key_name
        if modifiers:
            result["modifiers"] = modifiers
        return result
    return {"type": "unknown", "raw": s}


def parse_single_binding(token):
    token = token.strip()
    m = re.match(r'&(\w+)(.*)', token)
    if not m:
        return {"type": "unknown", "raw": token}
    behavior = m.group(1)
    params_str = m.group(2).strip()
    BEHAVIOR_MAP = {
        "kp": "kp", "trans": "trans", "none": "none",
        "to": "to", "mo": "mo", "mt": "mt", "lt": "lt",
        "bt": "bt", "bt_sel1_clr": "bt_clear",
        "bootloader": "bootloader", "sys_reset": "sys_reset",
        "studio_unlock": "studio_unlock", "app_layer": "app_layer",
        "sym_shift_altgr": "sym_shift_altgr",
    }
    for prefix in ("hrm", "mhhrm", "lbsk", "bsk", "bsl", "sc"):
        if behavior == prefix or behavior.startswith(prefix):
            BEHAVIOR_MAP[behavior] = prefix
            break
    if behavior.startswith("vim_"):
        BEHAVIOR_MAP[behavior] = behavior
    btype = BEHAVIOR_MAP.get(behavior, behavior)
    result = {"type": btype}
    values = extract_numeric_values(params_str)
    if btype == "kp" and values:
        decoded = decode_value(values[0])
        result.update(decoded)
        result["type"] = "kp"
    elif btype in ("hrm", "mhhrm", "lbsk", "bsk", "bsl"):
        if len(values) >= 2:
            result["tap"] = decode_value(values[0])
            result["hold"] = decode_value(values[1])
        elif values:
            result["tap"] = decode_value(values[0])
    elif btype == "sc":
        if len(values) >= 2:
            result["layer"] = values[0].strip()
            result["key"] = decode_value(values[1])
    elif btype in ("to", "mo", "mt", "lt"):
        if values:
            result["layer"] = values[0].strip()
    elif btype == "bt":
        result["params"] = [v.strip() for v in values]
    else:
        if values:
            result["params"] = [v.strip() for v in values]
    return result


def parse_bindings(bindings_str):
    tokens = re.split(r'(?=&\w)', bindings_str)
    result = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        result.append(parse_single_binding(token))
    return result


def _extract_balanced_braces(content, start):
    depth = 0
    i = start
    while i < len(content):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                return content[start:i], i + 1
        i += 1
    return content[start:], len(content)


def extract_layers(dts_content):
    layers = []
    keymap_blocks = []
    for km in re.finditer(r'(?<!\w)keymap\s*\{', dts_content):
        block_content, _ = _extract_balanced_braces(dts_content, km.end() - 1)
        keymap_blocks.append(block_content)
    standard_idx = 0
    for block_idx, km_content in enumerate(keymap_blocks):
        layer_opens = list(re.finditer(r'(\w+):\s*\w+\s*\{', km_content))
        for m in layer_opens:
            label = m.group(1)
            layer_content, _ = _extract_balanced_braces(km_content, m.end() - 1)
            dn = re.search(r'display-name\s*=\s*"([^"]+)"', layer_content)
            if not dn:
                continue
            display_name = dn.group(1)
            bd = re.search(r'bindings\s*=\s*<', layer_content)
            if not bd:
                continue
            bindings_start = bd.end()
            depth = 0
            pos = bindings_start
            while pos < len(layer_content):
                if layer_content[pos] == '<':
                    depth += 1
                elif layer_content[pos] == '>':
                    depth -= 1
                    if depth == 0:
                        break
                pos += 1
            bindings_raw = layer_content[bindings_start:pos]
            bindings = parse_bindings(bindings_raw)
            layer_type = "standard"
            if label.startswith("app_layer_"):
                layer_type = "app"
                try:
                    layer_id = int(label.replace("app_layer_", ""))
                except ValueError:
                    layer_id = len(layers)
            else:
                layer_id = standard_idx
                standard_idx += 1
            num_keys = len(bindings)
            cols = 14
            rows = num_keys // cols + (1 if num_keys % cols else 0)
            rows_data = []
            for r in range(rows):
                start = r * cols
                end = min(start + cols, num_keys)
                rows_data.append(bindings[start:end])
            layer = {
                "id": layer_id, "name": display_name, "label": label,
                "type": layer_type, "keys": bindings, "rows": rows_data,
            }
            layers.append(layer)
    return layers


def extract_transform(dts_content):
    m = re.search(r'(keymap_transform_\w+)\s*\{', dts_content)
    if not m:
        return None
    block_content, _ = _extract_balanced_braces(dts_content, m.end() - 1)
    cm = re.search(r'columns\s*=\s*<(\d+)>', block_content)
    rm = re.search(r'rows\s*=\s*<(\d+)>', block_content)
    if cm and rm:
        return {"rows": int(rm.group(1)), "cols": int(cm.group(1)),
                "split": True, "col_split": 6}
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_keymap.py <dts.pre> [-o output.json]")
        sys.exit(1)
    dts_path = Path(sys.argv[1])
    if not dts_path.exists():
        print("Error: file not found: " + str(dts_path))
        sys.exit(1)
    output_path = None
    if "-o" in sys.argv:
        idx = sys.argv.index("-o")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])
    dts_content = dts_path.read_text()
    transform = extract_transform(dts_content)
    layers = extract_layers(dts_content)
    result = {
        "layout": transform or {"rows": 5, "cols": 14, "split": True, "col_split": 6},
        "layers": layers,
    }
    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    if output_path:
        output_path.write_text(json_str)
        print("Written to " + str(output_path))
    else:
        print(json_str)
    print("\n--- Summary ---")
    print("Layout: " + str(result['layout']))
    print("Layers: " + str(len(layers)))
    for layer in layers:
        print("  [" + str(layer['id']) + "] " + layer['name'] + " (" + layer['type'] + ") - " +
              str(len(layer['keys'])) + " keys, " + str(len(layer['rows'])) + " rows")


if __name__ == "__main__":
    main()