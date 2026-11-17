"""Run actual KiCad checks and netlist cross-checks; never physical acceptance."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
REVIEW=ROOT/'review'; REVIEW.mkdir(exist_ok=True)
SCHEM=ROOT/'bin_monitor_carrier.kicad_sch'
BOARD=ROOT/'bin_monitor_carrier.kicad_pcb'

def run(args):
    result=subprocess.run([CLI,*map(str,args)],capture_output=True,text=True,check=True)
    print(result.stdout.strip())
    if result.stderr.strip(): print(result.stderr.strip())

run(['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',REVIEW/'erc.json',SCHEM])
run(['pcb','drc','--format','json','--severity-all','--exit-code-violations','--refill-zones','--save-board','--schematic-parity','-o',REVIEW/'drc.json',BOARD])
run(['sch','export','netlist','--format','kicadxml','-o',ROOT/'bin_monitor_carrier.net',SCHEM])

erc=json.loads((REVIEW/'erc.json').read_text())
erc_items=[item for sheet in erc.get('sheets',[]) for item in sheet.get('violations',[])]
erc_items+=erc.get('violations',[])
drc=json.loads((REVIEW/'drc.json').read_text())
assert not erc_items, erc_items
for key in ['violations','unconnected_items','schematic_parity']:
    assert not drc[key],(key,drc[key])

xml=ET.parse(ROOT/'bin_monitor_carrier.net').getroot()
pins={}
for net in xml.findall('./nets/net'):
    for n in net.findall('node'):
        pins[(n.attrib['ref'],n.attrib['pin'])]=net.attrib['name']
layout=json.loads((ROOT/'layout-manifest.json').read_text())
for key,value in layout['pad_nets'].items():
    ref,pin=key.split('.')
    assert pins[(ref,pin)]==value,(key,pins[(ref,pin)],value)
assert len(xml.findall('./components/comp'))==14
assert not (ROOT/'gerber').exists()
assert not list(ROOT.rglob('*.gbr')) and not list(ROOT.rglob('*.drl'))

tracked=[SCHEM,BOARD,ROOT/'bin_monitor_carrier.kicad_pro',ROOT/'BinMonitor.kicad_sym',ROOT/'fp-lib-table',ROOT/'sym-lib-table']+list((ROOT/'BinMonitor.pretty').glob('*.kicad_mod'))
record={
    'executed_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
    'kicad_version':subprocess.check_output([CLI,'version'],text=True).strip(),
    'design_revision':'v0.3 DRAFT','erc_violations':len(erc_items),
    'drc_violations':len(drc['violations']),'unconnected_items':len(drc['unconnected_items']),
    'schematic_parity_issues':len(drc['schematic_parity']),
    'netlist_assertions':len(layout['pad_nets']),'footprints':14,
    'board_nominal_mm':[50,38],'copper_layers':2,'thickness_mm':1.6,
    'physical_acceptance':'NOT RUN','hardware_inventory':'Neither module available',
    'cost_acceptance':'BLOCKED; carrier costs unquoted','fabrication_release':False,
    'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked},
}
(REVIEW/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
print('Verified: ERC0, DRC0, unrouted0, parity0; 21 intended net/pin assignments.')
