"""Derive a 14-pin carrier interface from Seeed's published XIAO library.

Run with the repository KiCad Python. Never changes global KiCad libraries.
"""
from pathlib import Path
import copy
import hashlib
import json
import sys
import sexpdata

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2]/'python'))
from utils.sexpr_format import prettify
LIBS = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport')
S = sexpdata.Symbol


def node(tag, *args):
    return [S(tag), *args]


def isnode(obj, tag):
    return isinstance(obj, list) and obj and str(obj[0]) == tag


def field(obj, tag):
    return next(x for x in obj if isnode(x, tag))


symbol_tree = sexpdata.loads((ROOT/'vendor-source/Seeed_Studio_XIAO_Series.kicad_sym').read_text())
symbol = copy.deepcopy(next(x for x in symbol_tree if isnode(x, 'symbol') and x[1] == 'XIAO-ESP32-C3-SMD'))
name = 'XIAO_ESP32C3_14P'
symbol[1] = name
for child in symbol:
    if isnode(child, 'property'):
        if child[1] == 'Reference': child[2] = 'A'
        if child[1] == 'Value': child[2] = name
        if child[1] == 'Footprint': child[2] = 'BinMonitor:XIAO_ESP32C3_14P_THT'
        if child[1] == 'Datasheet': child[2] = 'https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/'
    if isnode(child, 'symbol'):
        child[1] = child[1].replace('XIAO-ESP32-C3-SMD', name)
        child[:] = [x for x in child if not (isnode(x, 'pin') and int(field(x, 'number')[1]) > 14)]
        for pin in child:
            if not isnode(pin, 'pin'): continue
            number = int(field(pin, 'number')[1])
            if number <= 11: pin[1] = S('bidirectional')
            if number == 12: pin[1] = S('power_out')
            if number == 13: pin[1] = S('power_in')
            if number == 14: pin[1] = S('passive')
library = [S('kicad_symbol_lib'), node('version', 20241209), node('generator', 'kicad_symbol_editor'), symbol]
(ROOT/'BinMonitor.kicad_sym').write_text(prettify(sexpdata.dumps(library))+'\n')

pretty = ROOT/'BinMonitor.pretty'
pretty.mkdir(exist_ok=True)
footprint = sexpdata.loads((ROOT/'vendor-source/XIAO-ESP32-C3-DIP.kicad_mod').read_text())
footprint[1] = 'XIAO_ESP32C3_14P_THT'
filtered = []
for child in footprint:
    if isnode(child, 'model'): continue  # Vendor archive references unrelated local 3D paths.
    if isnode(child, 'pad'):
        if str(child[2]) != 'thru_hole': continue
        field(child, 'size')[1:] = [1.9, 1.9]
        field(child, 'drill')[1:] = [1.0]
        child[3] = S('rect') if child[1] == '1' else S('circle')
    if isnode(child, 'fp_rect') and field(child, 'layer')[1] == 'F.CrtYd': continue
    if any(isnode(child, tag) for tag in ['fp_line','fp_arc','fp_circle']):
        field(child, 'layer')[1] = 'F.Fab'
    if isnode(child, 'property') and child[1] == 'Reference':
        field(child, 'at')[1:] = [0, 10.5, 0]
    if isnode(child, 'property') and child[1] == 'Value':
        child[2] = 'XIAO_ESP32C3_14P_THT'
    filtered.append(child)
footprint = filtered
footprint.append(node('attr', S('through_hole')))
footprint.append(node('descr', 'Seeed XIAO ESP32C3 14-pin THT carrier; Seeed DIP pin coordinates; 1.0mm holes/1.9mm pads; verify header fit. No underside battery/JTAG contacts.'))
footprint.append(node('fp_rect', node('start', -10.8, -9.3), node('end', 12.4, 9.3), node('stroke', node('width', 0.05), node('type', S('default'))), node('fill', S('no')), node('layer', 'F.CrtYd')))
(pretty/'XIAO_ESP32C3_14P_THT.kicad_mod').write_text(sexpdata.dumps(footprint)+'\n')

copies = {
    'JST_XH_1x04': 'Connector_JST.pretty/JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical.kicad_mod',
    'C0805': 'Capacitor_SMD.pretty/C_0805_2012Metric.kicad_mod',
    'C0603': 'Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod',
    'R0603': 'Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod',
    'LED0603': 'LED_SMD.pretty/LED_0603_1608Metric.kicad_mod',
    'TestPad_1p5': 'TestPoint.pretty/TestPoint_Pad_D1.5mm.kicad_mod',
    'M2_Hole': 'MountingHole.pretty/MountingHole_2.2mm_M2.kicad_mod',
}
for local_name, source in copies.items():
    tree = sexpdata.loads((LIBS/'footprints'/source).read_text())
    tree[1] = local_name
    tree = [x for x in tree if not isnode(x, 'model')]
    (pretty/(local_name+'.kicad_mod')).write_text(sexpdata.dumps(tree)+'\n')

(ROOT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "BinMonitor")(type "KiCad")(uri "${KIPRJMOD}/BinMonitor.kicad_sym")(options "")(descr "Seeed-derived XIAO carrier interface")))\n')
(ROOT/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "BinMonitor")(type "KiCad")(uri "${KIPRJMOD}/BinMonitor.pretty")(options "")(descr "Project-local carrier footprints")))\n')

pins = {}
for child in symbol:
    if isnode(child, 'symbol'):
        for pin in child:
            if isnode(pin, 'pin'):
                pins[field(pin, 'number')[1]] = field(pin, 'name')[1]
assert pins['5'] == 'D4' and pins['6'] == 'D5' and pins['12'] == '3V3_OUT' and pins['13'] == 'GND'
manifest = {
    'seeed_footprints_url':'https://files.seeedstudio.com/wiki/XIAO-KiCad-Library/New_XIAO_Series_Footprints.zip',
    'seeed_symbols_url':'https://files.seeedstudio.com/wiki/XIAO-KiCad-Library/XIAO_Series_SCH_Symbols.zip',
    'pin_map':pins,
    'adaptations':['14 edge/header pins only; omit underside JTAG/battery contacts', 'GPIO bidirectional; 3V3 power_out; GND power_in', 'Seeed DIP pad centers unchanged', 'THT drill1.0mm pad1.9mm; actual header fit still requires verification', 'Move duplicate module silk to fab; courtyard includes USB outline', 'Remove nonportable and unrelated vendor3D model references'],
    'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'vendor-source').iterdir() if p.is_file()},
    'kicad_standard_copies':copies,
}
(ROOT/'library-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Prepared 14-pin module symbol, eight local footprints and relative library tables.')
