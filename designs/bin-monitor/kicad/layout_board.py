"""Rebuild the review layout from the MCP-synchronised unrouted board.

KiCad must not have this target board open during generation. No fabrication
outputs are produced. Run KiCad CLI DRC with refill/save after this script.
"""
from pathlib import Path
import json
import math
import pcbnew as p

ROOT = Path(__file__).resolve().parent
board = p.LoadBoard(str(ROOT/'bin_monitor_carrier.unrouted.kicad_pcb'))
mm = p.FromMM
vec = lambda xy: p.VECTOR2I(mm(xy[0]), mm(xy[1]))

placement = {
    'A1':(112.5,117.5,180), 'J1':(137,107.5,270),
    'C1':(132,120,90), 'C2':(134.5,120.2,90),
    'R1':(109.96,129,270), 'D1':(114,131,0),
    'TP1':(127,108,0), 'TP2':(127,111.5,0),
    'TP3':(128,130.5,0), 'TP4':(135,130.5,0),
    'H1':(103,103,0), 'H2':(147,103,0),
    'H3':(103,135,0), 'H4':(147,135,0),
}
fps = {fp.GetReference():fp for fp in board.GetFootprints()}
assert set(fps) == set(placement), (set(fps), set(placement))
for ref,(x,y,rotation) in placement.items():
    fp=fps[ref]
    fp.SetPosition(vec((x,y)))
    fp.SetOrientationDegrees(rotation)
    fp.Value().SetVisible(False)
    fp.Reference().SetTextSize(vec((0.85,0.85)))
    fp.Reference().SetTextThickness(mm(0.13))
    fp.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
    fp.Reference().SetPosition(vec((x,y-2)))
    if ref.startswith(('TP','H')):
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
    if ref=='A1':
        for graphic in fp.GraphicalItems():
            if graphic.GetLayer()==p.F_SilkS:
                graphic.SetLayer(p.F_Fab)

def pad(ref, number):
    return next(x for x in fps[ref].Pads() if x.GetNumber()==str(number))

def pos(ref, number):
    xy=pad(ref,number).GetPosition()
    return (p.ToMM(xy.x),p.ToMM(xy.y))

def segment(net, points, layer='F.Cu', width=0.25):
    code=board.FindNet(net).GetNetCode()
    for a,b in zip(points,points[1:]):
        if a==b: continue
        track=p.PCB_TRACK(board)
        track.SetStart(vec(a)); track.SetEnd(vec(b))
        track.SetLayer(board.GetLayerID(layer)); track.SetWidth(mm(width)); track.SetNetCode(code)
        board.Add(track)

def via(net, xy):
    item=p.PCB_VIA(board)
    item.SetPosition(vec(xy)); item.SetWidth(mm(0.6)); item.SetDrill(mm(0.3))
    item.SetViaType(p.VIATYPE_THROUGH); item.SetLayerPair(p.F_Cu,p.B_Cu)
    item.SetNetCode(board.FindNet(net).GetNetCode()); board.Add(item)

# Assert the electrical intent before adding any copper.
expected = {
    ('A1','3'):'LED_GPIO', ('A1','5'):'I2C_SDA', ('A1','6'):'I2C_SCL',
    ('A1','12'):'+3V3', ('A1','13'):'GND',
    ('J1','1'):'+3V3', ('J1','2'):'GND', ('J1','3'):'I2C_SDA', ('J1','4'):'I2C_SCL',
    ('C1','1'):'+3V3', ('C1','2'):'GND', ('C2','1'):'+3V3', ('C2','2'):'GND',
    ('R1','1'):'LED_GPIO', ('R1','2'):'LED_A', ('D1','2'):'LED_A', ('D1','1'):'GND',
    ('TP1','1'):'+3V3', ('TP2','1'):'GND', ('TP3','1'):'I2C_SDA', ('TP4','1'):'I2C_SCL',
}
for key,net in expected.items():
    assert pad(*key).GetNetname()==net, (key,pad(*key).GetNetname(),net)

# Sensor power: bottom-layer distribution, front decoupling next to connector.
segment('+3V3',[pos('A1',12),(109.96,108.5),(110.96,107.5),pos('J1',1)],'B.Cu',0.5)
segment('+3V3',[(127,107.5),(127,108)],'B.Cu',0.4)
via('+3V3',(127,108))
segment('+3V3',[pos('J1',1),(132,107.5),(129,110.5),(129,120.95),pos('C1',1),pos('C2',1)],'F.Cu',0.5)

# Keep the two I2C traces on separate layers at their crossing.
segment('I2C_SDA',[pos('A1',5),(115.04,127.5),(132,127.5),(140,119.5),(140,115.5),pos('J1',3)])
segment('I2C_SDA',[(128,127.5),pos('TP3',1)])
segment('I2C_SCL',[pos('A1',6),(117.58,127),(140,127),(143,124),(143,115),pos('J1',4)],'B.Cu')
segment('I2C_SCL',[(135,127),pos('TP4',1)],'B.Cu')
via('I2C_SCL',pos('TP4',1))

# Low-current, active-high LED on D2/GPIO4. R1 limits current to <=3.3mA
# even for a hypothetical zero-forward-drop LED at nominal3.3V.
segment('LED_GPIO',[pos('A1',3),pos('R1',1)])
segment('LED_A',[pos('R1',2),(109.96,132.5),(114.775,132.5),pos('D1',2)])

# Local returns connect into B.Cu ground; module ground exits the zone keepout.
segment('GND',[pos('A1',13),(107.42,106.5)],'B.Cu',0.5)
for ref,number,xy in [('C1',2,(132,117.8)),('C2',2,(134.5,118.2)),('D1',1,(112,131)),('TP2',1,(128,111.5))]:
    segment('GND',[pos(ref,number),xy],width=0.4)
    via('GND',xy)

zone=p.ZONE(board)
zone.SetLayer(p.B_Cu); zone.SetNetCode(board.FindNet('GND').GetNetCode())
zone.SetLocalClearance(mm(0.25)); zone.SetThermalReliefGap(mm(0.3))
zone.SetThermalReliefSpokeWidth(mm(0.3)); zone.SetMinThickness(mm(0.2))
zone.Outline().NewOutline()
for xy in [(100.6,100.6),(149.4,100.6),(149.4,137.4),(100.6,137.4)]:
    zone.Outline().Append(int(mm(xy[0])),int(mm(xy[1])))
board.Add(zone)

# No zone copper beneath the module; tracks are explicitly allowed.
keep=p.ZONE(board); keep.SetIsRuleArea(True)
layers=p.LSET(); layers.AddLayer(p.F_Cu); layers.AddLayer(p.B_Cu)
keep.SetLayerSet(layers)
keep.SetDoNotAllowZoneFills(True); keep.SetDoNotAllowTracks(False)
keep.SetDoNotAllowVias(False); keep.SetDoNotAllowPads(False); keep.SetDoNotAllowFootprints(False)
keep.SetZoneName('XIAO_BODY_NO_ZONE_COPPER')
keep.Outline().NewOutline()
for xy in [(101.7,108.3),(123.5,108.3),(123.5,127.7),(101.7,127.7)]:
    keep.Outline().Append(int(mm(xy[0])),int(mm(xy[1])))
board.Add(keep)

# Reserve a 5mm screw-head envelope at every M2 mounting position.
for ref in ['H1','H2','H3','H4']:
    hole_keep=p.ZONE(board); hole_keep.SetIsRuleArea(True)
    hole_keep.SetLayerSet(layers); hole_keep.SetDoNotAllowZoneFills(True)
    hole_keep.SetDoNotAllowTracks(True); hole_keep.SetDoNotAllowVias(True)
    hole_keep.SetDoNotAllowPads(False); hole_keep.SetDoNotAllowFootprints(False)
    hole_keep.SetZoneName(ref+'_M2_SCREW_CLEARANCE')
    hole_keep.Outline().NewOutline()
    x,y,_=placement[ref]
    for i in range(32):
        angle=2*math.pi*i/32
        hole_keep.Outline().Append(int(mm(x+2.5*math.cos(angle))),int(mm(y+2.5*math.sin(angle))))
    board.Add(hole_keep)

def text(content,xy,size=0.9,layer=p.F_SilkS,rotation=0):
    item=p.PCB_TEXT(board); item.SetText(content); item.SetPosition(vec(xy))
    item.SetTextSize(vec((size,size))); item.SetTextThickness(mm(0.13))
    item.SetLayer(layer); item.SetTextAngle(p.EDA_ANGLE(rotation,p.DEGREES_T)); board.Add(item)
    if layer in (p.B_Fab,p.B_SilkS): item.SetMirrored(True)

# Compact, meaningful on-board annotations.
def silk_line(a,b):
    shape=p.PCB_SHAPE(board); shape.SetShape(p.SHAPE_T_SEGMENT)
    shape.SetStart(vec(a)); shape.SetEnd(vec(b)); shape.SetLayer(p.F_SilkS)
    shape.SetWidth(mm(0.12)); board.Add(shape)
for a,b in [((102.075,108.6),(122.925,108.6)),((122.925,108.6),(122.925,126.4)),
            ((122.925,126.4),(102.075,126.4)),((102.075,126.4),(102.075,122)),
            ((102.075,113),(102.075,108.6)),((102.075,113),(100.45,113)),
            ((100.45,113),(100.45,122)),((100.45,122),(102.075,122))]:
    silk_line(a,b)
for ref,xy in {'A1':(112.5,106),'J1':(137,121.8),'C1':(131,123.3),'C2':(134.5,123.3),
               'R1':(107.7,129),'D1':(114,133.5),
               'TP1':(124.3,108),'TP2':(124.3,111.5),
               'TP3':(128,132.5),'TP4':(135,132.5)}.items():
    fps[ref].Reference().SetPosition(vec(xy))
for ref in ['H1','H2','H3','H4']:
    fps[ref].Reference().SetVisible(False)
text('BIN MONITOR v0.3',(125,103),1.1)
text('DRAFT - BENCH VERIFY',(126,136),0.8)
text('USB 5V',(103,118),0.8,rotation=90)
for label,y in [('1:3V3',107.5),('2:GND',110),('3:SDA',112.5),('4:SCL',115)]:
    text(label,(143, y),0.8)
text('STATUS',(119,133.5),0.8)
text('50x38mm / 2 layer / 1.6mm',(125,119),1.0,layer=p.B_Fab)
text('DRAFT ONLY - NO FAB RELEASE',(125,122),0.8,layer=p.B_Fab)

board.SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(mm(1.6))
board.GetTitleBlock().SetTitle('Bin Monitor XIAO Carrier')
board.GetTitleBlock().SetRevision('v0.3 DRAFT')
board.GetTitleBlock().SetDate('2026-11-17')
p.SaveBoard(str(ROOT/'bin_monitor_carrier.kicad_pcb'),board)
manifest={
    'board_mm':{'x':100,'y':100,'width':50,'height':38,'corner_radius':2,'thickness':1.6},
    'layers':2,'placement':placement,'pad_nets':{f'{ref}.{number}':net for (ref,number),net in expected.items()},
    'tracks':len(list(board.GetTracks())), 'ground_zone':'B.Cu',
    'physical_validation':'NOT RUN','fabrication_release':False,
}
(ROOT/'layout-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Saved review board:14 footprints, fully planned routes; CLI refill/DRC still required.')
for ref in ['A1','J1','C1','C2','R1','D1']:
    print(ref,{pad.GetNumber():[round(p.ToMM(pad.GetPosition().x),3),round(p.ToMM(pad.GetPosition().y),3),pad.GetNetname()] for pad in fps[ref].Pads()})
