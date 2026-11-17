"""Rebuild the engineering tables and diagrams from the reviewed design inputs."""

from pathlib import Path
import csv
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parent
DATE = "2026-11-17"


def table(name, fields, rows):
    path = ROOT/name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


SOURCES = [
    ("S01", "Seeed XIAO ESP32C3 guide and pin map", "https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/", "D4 GPIO6 SDA; D5 GPIO7 SCL; 3V3 output; USB-C; included antenna"),
    ("S02", "Pololu 3415 VL53L1X carrier", "https://www.pololu.com/product/3415", "Carrier voltage/logic; XSHUT; price USD22.95 qty1 before tax/shipping"),
    ("S03", "Espressif ESP32-C3 datasheet v2.5", "https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf", "Section5.6.1 RF TX reference 335mA; not whole-board guaranteed maximum"),
    ("S04", "ST VL53L1X DS12385 Rev8", "https://www.st.com/resource/en/datasheet/vl53l1x.pdf", "Sections7.3-7.6; range/ambient/ROI/error tradeoff; 40mm minimum"),
    ("S05", "DFRobot SEN0311 A02YYUW specifications", "https://wiki.dfrobot.com/sen0311/", "3-450cm flat object; 60degree angle; UART; alternate only"),
    ("S06", "Espressif ESP32-C3-DevKitM-1 guide", "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c3/esp32-c3-devkitm-1/user_guide.html", "Backup controller; N4X ordering; old non-N4X EOL"),
    ("S07", "Pololu 3692 VL53L4CD carrier specifications", "https://www.pololu.com/product/3692/specs", "1.2m nominal maximum; excludes 1.3m empty bin geometry"),
    ("S08", "ST VL53L4CD DS13812 Rev8", "https://www.st.com/resource/en/datasheet/vl53l4cd.pdf", "Tables16/17 reflectance-dependent range and accuracy"),
    ("S09", "LINE retry API requests", "https://developers.line.biz/en/docs/messaging-api/retrying-api-request/", "Same retry key/body/recipient; 24h retry window; accepted200/409"),
    ("S10", "LINE group chats", "https://developers.line.biz/en/docs/messaging-api/group-chats/", "Group join and webhook groupId; requires authorized setup"),
    ("S11", "LINE sending messages", "https://developers.line.biz/en/docs/messaging-api/sending-messages/", "Push messages and group recipient-based message counting"),
    ("S12", "Pololu carrier schematic", "https://www.pololu.com/file/0J1188/vl53l0x-vl53l1x-vl53l3cx-vl53l4cd-time-of-flight-sensor-schematic.pdf", "Carrier regulator, I2C shifting and internal pullups; use silkscreen labels"),
    ("S13", "Seeed XIAO ESP32C3 SKU113991054 listing", "https://www.seeedstudio.com/Seeed-XIAO-ESP32C3-p-5431.html", "USD4.90 displayed single unit; unsoldered header variant; before tax/shipping"),
    ("S14", "Seeed XIAO official symbol and footprint archives", "https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/#resources", "Project-local derivative14-pin symbol/THT pattern; source hashes in kicad/library-provenance.json"),
    ("S15", "JST XH connector datasheet", "https://www.jst-mfg.com/product/pdf/eng/eXH.pdf", "B4B-XH-A board header; XHP-4 housing and SXH-001T-P0.6 contacts;2.5mm pitch"),
    ("S16", "TDK C2012X5R1A106K085AB", "https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no=C2012X5R1A106K085AB", "C1 10uF10V X5R0805; sourcing and effective capacitance to verify"),
    ("S17", "Murata MLCC component listing", "https://www.murata.com/-/media/webrenewal/tool/library/common-pdf/static-model/component-list-s-mlcc-2506.ashx?cvid=20250805040438000000&la=ko-kr", "C2 GRM188R71C104KA01D100nF16V X7R0603; package suffixD"),
    ("S18", "Yageo RC0603FR-071KL spec sheet", "https://yageogroup.com/component-documentation/download/specsheet/RC0603FR-071KL", "R1 1k1%0.1W0603"),
    ("S19", "Kingbright APT1608SGC datasheet", "https://www.kingbrightusa.com/images/catalog/SPEC/APT1608SGC.pdf", "Green0603 LED; typical2.2V at20mA; actual low-current brightness NOT RUN"),
]

table("references/sources.csv", ["id", "title", "url", "use", "access_date"],
      [(*row, DATE) for row in SOURCES])

table("interface-table.csv", ["net", "controller", "sensor_or_destination", "voltage", "direction", "configuration", "source", "verification"], [
    ("USB_5V", "USB-C connector", "Qualified USB supply", "4.75-5.25V", "Supply to controller", "Only power input; battery and 5V/3V3 header injection unused", "S01;IN-05", "Design reviewed; physical test NOT RUN"),
    ("SENSOR_3V3", "3V3", "Pololu3415 VIN", "3.3V", "Controller rail to carrier", "Do not substitute carrier VDD; no 5V VIN with direct I2C", "S01;S02;S12", "Silkscreen mapping verified; HW-02 NOT RUN"),
    ("GND", "GND", "Pololu3415 GND", "0V", "Common return", "Short common ground; no isolated supplies", "S01;S02", "Physical continuity NOT RUN"),
    ("I2C_SDA", "D4 / GPIO6", "Pololu3415 SDA", "3.3V carrier-side bus", "Bidirectional open drain", "100kHz initial; use carrier onboard pullups; verify waveform", "S01;S02;S12", "Pin map checked; rise-time NOT RUN"),
    ("I2C_SCL", "D5 / GPIO7", "Pololu3415 SCL", "3.3V carrier-side bus", "Controller open drain clock", "100kHz; do not enable external JTAG on shared pins", "S01;S02;S12", "Pin map checked; waveform NOT RUN"),
    ("TOF_XSHUT_OPTION", "D1 / GPIO3", "Pololu3415 XSHUT", "Carrier pullup to2.8V", "Optional controller open drain", "Drive low or high impedance only; never actively drive high", "S01;S02;S12", "Optional fifth wire; NOT RUN"),
    ("TOF_GPIO1", "Not connected", "Pololu3415 GPIO1", "2.8V open drain output", "Unused", "Polling prototype; leave unconnected", "S02", "No MCU connection"),
    ("TOF_VDD", "Not connected", "Pololu3415 VDD", "2.8V regulator output", "Unused", "Do not connect to3V3 while VIN is powered", "S02", "No MCU connection"),
    ("LOCAL_DIAGNOSTIC", "USB-C native serial", "Maintenance host", "USB", "Bidirectional", "Status/calibration/logs; host replaces wall supply during service", "S01;OPS-01", "Firmware and access NOT RUN"),
    ("WIFI", "Included external antenna", "2.4GHz AP", "RF", "Bidirectional", "Keep antenna out of metal obstruction; no LINE credentials on device", "S01;IN-06", "Coverage NOT RUN"),
    ("CARRIER_J1", "A1 pad12/13/5/6", "J1 pins1/2/3/4 =3V3/GND/SDA/SCL", "3.3V", "Power and I2C", "v0.3 carrier interface; Pololu end wired by silkscreen, not same numerical order", "S01;S02;S14;S15", "ERC/DRC/netlist checked separately; physical test NOT RUN"),
    ("CARRIER_STATUS", "D2 / GPIO4 / A1 pad3", "R1 1k toD1 anode; D1 cathodeGND", "3.3V active high", "Controller output", "Added v0.3; does not use D1/GPIO3 optional XSHUT", "S01;S18;S19", "Firmware/brightness NOT RUN"),
])

table("bom.csv", ["reference", "manufacturer", "mpn_or_sku", "qty", "value", "footprint", "datasheet_or_spec", "unit_usd", "price_type", "price_source", "price_date", "alternative", "missing_or_blocked"], [
    ("A1", "Seeed Studio", "113991054", 1, "XIAO ESP32C3; antenna and two7pin headers included; not owned", "BinMonitor:XIAO_ESP32C3_14P_THT", SOURCES[0][2], "4.90", "Published qty1; unsoldered headers; excludes tax/shipping", SOURCES[12][2], DATE, "ESP32-C3-DevKitM-1-N4X; separate quote/interface needed", "Confirm actual board revision, header fit and supplied parts"),
    ("A2 offboard", "Pololu", "3415", 1, "VL53L1X regulated/level-shifted carrier; not owned", "Offboard module; harness toJ1, no carrier landpattern", SOURCES[1][2], "22.95", "Published qty1; excludes tax/shipping", SOURCES[1][2], DATE, "SEN0311 alternate principle; not drop-in", "130cm dark-bottom and SEN-02/SEN-07 NOT RUN"),
    ("P1", "TBD", "TBD", 1, "Qualified regulated5V USB supply >=2A", "External module", "TBD actual product datasheet", "", "USD6 allocation only", "Not quoted", DATE, "Existing qualified supply may be reused", "Actual manufacturer/MPN/safety documentation missing"),
    ("W1", "TBD", "TBD", 1, "USB power/data cable to USB-C", "Cable", "TBD actual cable rating", "", "USD3 allocation only", "Not quoted", DATE, "Existing verified data cable", "Connector on supply end and cable resistance unverified"),
    ("W2", "TBD", "TBD", 1, "Short four/five-wire harness; included module headers where supplied", "Wired prototype", "TBD wire/contact specification", "", "USD2 allocation only", "Not quoted", DATE, "Soldered short leads", "Strain relief and actual connector/contact MPN missing"),
    ("M1", "TBD", "TBD", 1, "Removable nonconductive bracket, screws and protective controller mount", "Mechanical assembly", "TBD measured mounting drawing", "", "USD5 allocation only", "Not quoted", DATE, "Use existing suitable fixture", "No photo/depth/bottom geometry; mechanical design BLOCKED"),
    ("J1", "JST", "B4B-XH-A(LF)(SN)", 1, "4pin2.5mm vertical sensor header", "BinMonitor:JST_XH_1x04", SOURCES[14][2], "", "Unquoted", "Official specification only", DATE, "Not a generic JST2.54 connector", "Mating harness/strain relief physical check NOT RUN"),
    ("J2 offboard", "JST", "XHP-4", 1, "4way XH mating housing", "Offboard harness", SOURCES[14][2], "", "Unquoted", "Official specification only", DATE, "TBD verified assembled harness", "Requires4 crimp contacts and correctly mapped sensor-end wires"),
    ("J2 contacts", "JST", "SXH-001T-P0.6", 4, "XH crimp contact", "Offboard harness", SOURCES[14][2], "", "Unquoted", "Official specification only", DATE, "TBD verified assembled harness", "Confirm selected wire gauge/insulation with manufacturer specification"),
    ("C1", "TDK", "C2012X5R1A106K085AB", 1, "10uF10V X5R10%", "BinMonitor:C0805", SOURCES[15][2], "", "Unquoted", "Official specification only", DATE, "Same size/value/voltage after DC-bias check", "DC-bias, transient/inrush NOT RUN"),
    ("C2", "Murata", "GRM188R71C104KA01D", 1, "100nF16V X7R10%", "BinMonitor:C0603", SOURCES[16][2], "", "Unquoted", "Official specification only", DATE, "Same value/voltage0603", "Actual sourcing/version pending"),
    ("R1", "Yageo", "RC0603FR-071KL", 1, "1k1%0.1W", "BinMonitor:R0603", SOURCES[17][2], "", "Unquoted", "Official specification only", DATE, "Same value/tolerance/power0603", "Actual sourcing pending"),
    ("D1", "Kingbright", "APT1608SGC", 1, "Green LED; active high viaR1", "BinMonitor:LED0603", SOURCES[18][2], "", "Unquoted", "Official specification only", DATE, "Verify cathode pad1 for any alternate", "Brightness and firmware NOT RUN"),
    ("PCB1", "TBD", "bin_monitor_carrier v0.3 DRAFT", 1, "50x38mm2layer1.6mm draft only", "Carrier PCB", "kicad/README.md", "", "Unquoted; no fabrication release", "Not ordered", DATE, "Module-only prototype remains possible", "PCB/assembly cost and mechanical fit BLOCKED"),
])

table("cost-budget.csv", ["category", "usd", "basis", "status"], [
    ("Core device modules", "27.85", "A1=4.90 + A2=22.95 official web prices before shipping/tax", "Price snapshot; not purchased"),
    ("Enclosure and mounting", "5.00", "Allocation, no quote", "BLOCKED"),
    ("Power supply", "6.00", "Allocation, no quote", "BLOCKED"),
    ("USB cable and harness", "5.00", "Allocations3+2, no quote", "BLOCKED"),
    ("Original module-only prototype estimate", "43.85", "27.85 modules +16.00 allocations; excludes added carrier", "Historical planning estimate, not current carrier total"),
    ("Carrier PCB and added components", "", "J1/mate/contacts/C1/C2/R1/D1/barePCB need quotes; avoid double-counting harness allocations", "BLOCKED"),
    ("Current carrier hardware total", "", "Must be <USD50; cannot assert compliance without quotes", "BLOCKED"),
    ("Shipping and tax", "", "All-in cost scope and quotes missing", "BLOCKED"),
    ("Assembly and test labor/tools", "", "Separate from device parts; scope/cost unquoted", "BLOCKED"),
    ("Backend recurring", "", "Deployment and existing hosting unknown", "BLOCKED"),
    ("LINE recurring", "", "Account plan, group size and usage unknown", "BLOCKED"),
])

table("power-budget.csv", ["load", "rail_v", "allocated_peak_ma", "datasheet_reference_ma", "basis", "measured"], [
    ("XIAO complete controller", "3.3", "400", "335", "335mA ESP32-C3 RF test reference S03; remainder board overhead allocation, not guaranteed max", "NOT RUN"),
    ("VL53L1X carrier", "3.3 VIN", "40", "40", "Pololu S02 peak; typical active20mA; configuration-dependent", "NOT RUN"),
    ("Contingency", "3.3", "60", "", "Design allocation", "NOT RUN"),
    ("3V3 budget total", "3.3", "500", "", "1.65W rail budget; must verify regulator thermal/transient capacity", "NOT RUN"),
    ("USB input planning allowance", "5.0", "600", "", "3W input allowance; conversion/board performance not measured", "NOT RUN"),
    ("External supply minimum rating", "5.0", "2000", "", "IN-05 supply capability, not actual consumption", "NOT RUN"),
])

tests = {
    "SEN-01": ("H持久化與未校正", "空桶確認後取10筆有效值校正；保存H及設定版本；斷電重啟；再注入校正失敗。", "H重啟保留；失敗顯示未校正且不產生滿載事件。", "量尺、實物、USB日誌", "NOT RUN"),
    "SEN-02": ("逐筆距離精度", "以實際H重算四測點；名義H130cm為104/65/26/13cm；平面靶各10次，記所有status與實測值，無效值不偷偷刪除。", "每次距離誤差≤20mm；若有無效值不能宣稱整批通過。另驗證130cm空桶底。", "平面靶、量尺、受控光照", "NOT RUN"),
    "SEN-03": ("持續滿載", "記錄首次有效濾波F≥80%的時間；分別在59秒移開及維持60秒；記事件數。", "59秒不確認；連續60秒確認1事件；invalid或低於80重置計時。", "時間戳日誌、靶架", "NOT RUN"),
    "SEN-04": ("短暫遮擋", "正常狀態遮擋10秒後移除，重複20次；等待恢復後再下一次。", "20次誤發滿載通知均為0。", "遮擋物、事件及通知日誌", "NOT RUN"),
    "SEN-05": ("清空與遲滯", "滿載後置F≤50%並維持120秒；測119秒中斷、invalid、50<F<80；再進第二次滿載。", "僅完整120秒清空後重新待命；中間區保持鎖存；下一輪新event_id。", "靶架、狀態日誌", "NOT RUN"),
    "SEN-06": ("感測故障", "斷開感測器、注入通訊超時、超量程，各3次；獨立watchdog運行；恢復後重收樣本。", "無效即中斷持續計時；連續30秒無有效值全部SENSOR_FAULT，不產生新滿載事件。", "故障注入、邏輯分析/日誌", "NOT RUN"),
    "SEN-07": ("真實垃圾", "袋裝垃圾、紙類、塑膠容器各10次滿載/清空循環；用測點標線和量尺確認真值並拍照。", "滿載識別≥29/30；清空識別另≥29/30；保留全部結果，不宣稱容積準確。", "三類垃圾、量尺、照片", "NOT RUN"),
    "SEN-08": ("桶蓋條件", "使用者已確認無蓋，20次開關蓋子測試不適用；實際投放及支架遮擋仍在SEN-04/HW-03驗證。", "N/A僅適用蓋子子測試；若日後加蓋需重新啟用並驗證。", "使用者無蓋確認", "N/A"),
    "MSG-01": ("群組可達", "由負責人配置官方帳號、群組加入及簽章webhook；核對groupId；另獲指示後在指定測試群組發1則。", "人工確認群組可見並保存遮蔽證據。", "已授權測試帳號、群組、受控後端", "BLOCKED"),
    "MSG-02": ("訊息內容", "核對裝置號、位置、原偵測時間、時間品質、估計高度占比及清運文字；復網訊息標延遲。", "所有欄位正確；明示高度非容積；無token/密碼/群組私人內容。", "測試群組與遮蔽日誌", "BLOCKED"),
    "MSG-03": ("健康連線時效", "網路及額度正常，從首筆有效滿載濾波值計時，滿載60秒後傳送；10次記API與群組可見時刻。", "10/10群組可見≤90秒；不把200當可見證據。", "同步時鐘、裝置/服務日誌、群組觀察", "BLOCKED"),
    "MSG-04": ("重複抑制", "保持滿載2小時，重啟裝置及後端；注入API回應遺失；核對event_id與retry_key。", "同次滿載僅1則通知；重試不建立新key，保留接受證據。", "可控後端、測試群組", "BLOCKED"),
    "MSG-05": ("斷網補送", "滿載事件待送時斷網10分鐘並保持滿載；復網先同步最新狀態，再重新取樣確認及送出。", "復網120秒內恰1則；含原事件時間及延遲標記。", "Wi-Fi控制、持久化日誌、測試群組", "BLOCKED"),
    "MSG-06": ("清空與過期取消", "兩獨立案例：斷網中完成清空後復網；事件年齡>24小時後復網；再測取消與重播順序。", "兩案均不發舊滿載，保留取消原因；舊revision不能覆蓋新清空。", "可控時鐘、持久佇列、網路代理", "BLOCKED"),
    "MSG-07": ("API錯誤", "注入timeout/5xx/已接受409/401/群組錯誤/額度不足429與速率429；記排程。", "暫時錯誤受控退避且同key同本文；永久錯誤顯示異常；無快速無限重試。", "模擬LINE adapter及授權測試群組", "BLOCKED"),
    "MSG-08": ("三種重啟", "滿載已通知、滿載待送、正常各重啟3次；覆蓋儲存與送出/接收回應之間掉電點。", "不重複、不遺失；新樣本確認後才補送；未知時鐘不捏造時間。", "可控斷電、flash journal、測試群組", "BLOCKED"),
    "HW-01": ("電源角落", "在裝置端輸入4.75/5.00/5.25V各30分鐘，同時量測和Wi-Fi傳送；量啟動/發射峰值及3V3。", "無異常重啟；保存峰值/平均電流、最低軌壓及溫升；不只看供應器額定。", "合格低壓測試源、電流量測、示波器", "NOT RUN"),
    "HW-02": ("電壓相容", "以實物版本核對供電、GPIO和connector mapping；上電前通斷檢查；量SDA/SCL/XSHUT電位。", "carrier VIN3V3、bus3V3；XSHUT低/高阻態；無5V進不耐受腳位。", "實物datasheet、萬用表、示波器", "NOT RUN"),
    "HW-03": ("固定與清潔", "安裝照片與實際H；做10次換袋及擦拭，檢查支架、線材、天線、投放與光路。", "不鬆脫，不妨礙清運，感測路徑無遮擋；若位移重新校正。", "實桶、支架、照片", "NOT RUN"),
    "OPS-01": ("狀態辨識", "以USB診斷依次產生正常/滿載/網路或通知異常/感測異常/未校正；含並存錯誤。", "各狀態可區分；充電LED不冒充應用狀態；安裝後可存取診斷。", "主機、韌體診斷介面", "NOT RUN"),
    "OPS-02": ("七天可追溯", "保留7天狀態/通知紀錄；測環形容量、斷網、重啟、回收及錯誤暴增；raw於測試主機收集。", "能取回至少最近7天狀態與通知；含原/濾波距離、切換、event_id及結果。", "本機儲存與後端、日誌匯出", "NOT RUN"),
    "OPS-03": ("時間與憑證", "測未同步/時鐘跳變/掉電離線；稽核repo、診斷及HTTP log；只用受控假憑證測漏記。", "Asia/Taipei顯示；未同步明示；順序保留；無token/密碼/私人群組內容。", "可控NTP、遮蔽檢查", "NOT RUN"),
    "REL-01": ("七十二小時", "連續72小時無人工重啟；含≥24小時已知未滿，每日滿載/清空；全程紀錄。", "未滿期間誤發0；無人工重啟；保存每日循環及所有異常。", "實物、穩定供電、受控群組、測試員", "NOT RUN"),
}

req_rows = re.findall(r"^\| ((?:SEN|MSG|HW|OPS|REL)-\d+) \| (.*?) \| (.*?) \|$", (ROOT/"requirements.md").read_text(), re.M)
assert {row[0] for row in req_rows} == set(tests), "Missing or unexpected acceptance requirement"
assert len(req_rows) == 23
trace_rows = []
plan = ["# 需求追溯與驗收計畫", "", "所有實體及LINE測試未執行。BLOCKED是缺少先決條件；N/A只用於無蓋子測試。模擬結果另存，不替代以下驗收。", "", "名義H=130cm；測試必須使用安裝後實際校正H重算距離。原附件及使用者變更見requirements.md和requirements-update.md。", ""]
for req_id, name, original_acceptance in req_rows:
    title, steps, acceptance, equipment, status = tests[req_id]
    evidence = f"evidence/{req_id}/"
    trace_rows.append((req_id, name, original_acceptance, title, steps, acceptance,
                       equipment, status, "NOT RUN" if status != "N/A" else "N/A", evidence))
    plan += [f"## {req_id} {title}", "", f"狀態：**{status}**。證據預定位置：`{evidence}`。", "", f"步驟：{steps}", "", f"判定：{acceptance}", "", f"工具／先決條件：{equipment}。", ""]
plan += ["## 證據規則", "", "每次實測資料夾包含時間與時區、硬體/韌體/設定版本、操作者、校正H、設定、原始資料、預期與實際、PASS/FAIL理由。保留失敗與無效值，不篩掉不利樣本。敏感內容遮蔽。未執行不得標PASS。", "", "依使用者後續指示，v0.3已先建立KiCad載板草案。ERC/DRC靜態結果見kicad/review/validation.json；不可提升上述實體需求狀態。基線簽核、實物電氣、功能與預算驗收仍各自進行。", ""]
(ROOT/"test-plan.md").write_text("\n".join(plan))
table("traceability.csv", ["requirement_id", "requirement", "original_acceptance", "test", "steps", "acceptance_for_updated_bin", "equipment_and_dependencies", "readiness", "execution_status", "planned_evidence"], trace_rows)

height = 1300
thresholds = [(pct, round(height*(1-pct/100), 6)) for pct in (0,20,50,80,90)]
table("geometry.csv", ["fill_height_pct", "distance_mm", "basis"], [(pct,d,"Nominal H=1300mm; replace with calibrated H") for pct,d in thresholds])
validation_path=ROOT/'kicad/review/validation.json'
validation=json.loads(validation_path.read_text()) if validation_path.exists() else {}
validated=bool(validation) and all(hashlib.sha256((ROOT/'kicad'/name).read_bytes()).hexdigest()==digest for name,digest in validation.get('sha256',{}).items())
profile = {
    "schema_version": 1, "design_revision": "v0.3-carrier-draft", "date": DATE,
    "user_inputs": {"bin_height_cm":130, "width_cm":70, "lid":False, "hardware_budget_usd_exclusive":50},
    "inventory":{"controller_owned":False,"sensor_owned":False},
    "assumptions": {"nominal_effective_height_mm":1300, "effective_height_measured":False, "indoors_dry":True, "wifi_2_4ghz":True},
    "controller":{"manufacturer":"Seeed Studio", "sku":"113991054", "sda_gpio":6, "scl_gpio":7, "optional_xshut_gpio":3},
    "sensor":{"manufacturer":"Pololu", "sku":"3415", "ic":"VL53L1X", "vin_v":3.3, "i2c_address_7bit":"0x29", "i2c_hz":100000, "mode":"long", "timing_budget_ms":100, "roi":"full", "field_validated":False},
    "detector":{"sample_period_s":5,"median_samples":3,"full_threshold_pct":80,"full_hold_s":60,"clear_threshold_pct":50,"clear_hold_s":120,"sensor_fault_s":30},
    "proposals":{"clear_window_on_invalid":True,"resend_requalify_full_s":60,"model_max_sample_gap_s":7.5},
    "known_module_subtotal_usd":27.85,"module_only_accessory_allocations_usd":16,"module_prototype_estimate_usd":43.85,
    "planned_hardware_usd":None,"cost_acceptance":"BLOCKED; carrier components and PCB unquoted",
    "carrier":{"project":"kicad/bin_monitor_carrier.kicad_pro","board_mm":[50,38],"layers":2,"status_led_gpio":4,"sensor_j1":{"1":"+3V3","2":"GND","3":"I2C_SDA","4":"I2C_SCL"}},
    "custom_pcb_created":True,"erc":"PASS_STATIC" if validated else "NOT RUN_OR_STALE","drc":"PASS_STATIC" if validated else "NOT RUN_OR_STALE","product_accepted":False,
}
(ROOT/"design-profile.json").write_text(json.dumps(profile,indent=2,ensure_ascii=False)+"\n")
(ROOT/"event-example.json").write_text(json.dumps({
    "example_only":True,"device_id":"BIN-001","revision":42,"boot_id":"example-boot-id",
    "event_id":"00000000-0000-4000-8000-000000000001","event_type":"FULL",
    "height_state":"FULL","sensor_health":"OK","sample_age_ms":200,
    "calibration_h_mm":1300,"filtered_distance_mm":195,"estimated_height_pct":85,
    "clock_quality":"UNSYNCED","detected_at_utc":None,"detected_monotonic_ms":70000,
    "timezone":"Asia/Taipei","reconfirmed_after_reconnect":False,"cancelled_event_ids":[],
},indent=2)+"\n")

def svg_header(width, height, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#456179"/></marker></defs>
<style>text{{font-family:Arial,sans-serif;fill:#18334c}}.box{{fill:#f4f8fb;stroke:#adc3d5;stroke-width:2}}.line{{fill:none;stroke:#456179;stroke-width:2;marker-end:url(#arrow)}}.small{{font-size:16px}}.head{{font-size:23px;font-weight:bold}}</style>
<rect width="100%" height="100%" fill="white"/>
'''

overview = svg_header(1180,670,"Bin monitor prototype architecture")+'''
<text x="40" y="46" font-size="30" font-weight="bold">Bin full-height monitor · Architecture v0.3</text>
<text x="40" y="79" class="small">130 cm tall · 70 cm wide · no lid · hardware target below US$50</text>
<rect class="box" x="40" y="150" width="235" height="130" rx="12"/><text x="60" y="185" class="head">VL53L1X carrier</text><text x="60" y="218" class="small">Pololu 3415 · 3.3 V VIN</text><text x="60" y="248" class="small">5-second fresh samples</text>
<rect class="box" x="355" y="150" width="255" height="130" rx="12"/><text x="375" y="185" class="head">XIAO ESP32C3</text><text x="375" y="218" class="small">Median / hold timers / journal</text><text x="375" y="248" class="small">Wi-Fi · local diagnostics</text>
<path class="line" d="M275 215 H350"/><text x="284" y="197" class="small">I²C</text>
<rect class="box" x="710" y="150" width="220" height="130" rx="12"/><text x="730" y="185" class="head">Notify backend</text><text x="730" y="218" class="small">Durable event + retry key</text><text x="730" y="248" class="small">LINE token stays here</text>
<path class="line" d="M610 215 H705"/><text x="623" y="197" class="small">HTTPS</text>
<rect class="box" x="710" y="350" width="220" height="95" rx="12"/><text x="733" y="388" class="head">LINE API</text><text x="733" y="418" class="small">Messaging API push</text><path class="line" d="M820 280 V345"/>
<rect class="box" x="980" y="350" width="160" height="95" rx="12"/><text x="1000" y="388" class="head">Test group</text><text x="1000" y="418" class="small">Visible receipt</text><path class="line" d="M930 399 H975"/>
<rect class="box" x="355" y="350" width="255" height="95" rx="12"/><text x="375" y="388" class="head">Qualified USB 5 V</text><text x="375" y="418" class="small">Supply capability at least 2 A</text><path class="line" d="M482 350 V285"/>
<text x="40" y="505" class="head">Decision thresholds at nominal H = 130 cm</text>
<text x="40" y="540" class="small">FULL: d ≤ 26 cm for 60 s. CLEAR: d ≥ 65 cm for 120 s. Invalid samples reset both timers.</text>
<text x="40" y="572" class="small">30 s without valid readings → SENSOR_FAULT. Preserve the full-event latch across faults and reboots.</text>
<text x="40" y="615" class="small">DRAFT: physical tests and LINE acceptance NOT RUN. Actual H requires calibration. Height estimate is not volume.</text>
</svg>'''
(ROOT/"system-overview.svg").write_text(overview)
wiring = svg_header(1100,620,"Prototype wiring by verified module labels")+'''
<text x="40" y="46" font-size="30" font-weight="bold">Prototype wiring · connect by silkscreen labels</text>
<text x="40" y="80" class="small">Logical diagram only; terminal positions are not physical connector pin order.</text>
<rect class="box" x="60" y="130" width="300" height="340" rx="12"/><text x="85" y="170" class="head">Seeed XIAO ESP32C3</text>
<rect class="box" x="710" y="130" width="330" height="340" rx="12"/><text x="735" y="170" class="head">Pololu 3415 carrier</text>
<text x="100" y="225" font-size="20">3V3</text><text x="740" y="225" font-size="20">VIN (3.3 V)</text><path d="M360 219 H710" stroke="#d24a42" stroke-width="4"/>
<text x="100" y="275" font-size="20">GND</text><text x="740" y="275" font-size="20">GND</text><path d="M360 269 H710" stroke="#34404a" stroke-width="4"/>
<text x="100" y="325" font-size="20">D4 / GPIO6</text><text x="740" y="325" font-size="20">SDA</text><path d="M360 319 H710" stroke="#2879bc" stroke-width="4"/>
<text x="100" y="375" font-size="20">D5 / GPIO7</text><text x="740" y="375" font-size="20">SCL</text><path d="M360 369 H710" stroke="#23865b" stroke-width="4"/>
<text x="100" y="425" font-size="20">D1 / GPIO3 (optional)</text><text x="740" y="425" font-size="20">XSHUT (2.8 V pull-up)</text><path d="M360 419 H710" stroke="#9c6cc1" stroke-width="3" stroke-dasharray="8 5"/>
<text x="385" y="445" class="small">Optional: LOW / high impedance only</text>
<text x="60" y="515" class="small">Power controller only through USB-C. Leave sensor VDD and GPIO1 disconnected in this prototype.</text>
<text x="60" y="550" class="small">Carrier I²C pull-ups follow VIN: keep VIN at 3.3 V. Start at 100 kHz with short wires.</text>
<text x="60" y="585" class="small">Direct bench wiring reference. Carrier J1 uses four wires only; optional XSHUT is not fitted.</text>
</svg>'''
(ROOT/"prototype-wiring.svg").write_text(wiring)

geometry = svg_header(1100,720,"Nominal bin geometry and ranging thresholds")+'''
<text x="40" y="45" font-size="30" font-weight="bold">Bin geometry · nominal H = 130 cm</text>
<text x="40" y="78" class="small">No lid. Sensor on a rigid central support, pointing vertically down.</text>
<path d="M135 150 V540 H345 V150" fill="#f4f8fb" stroke="#47647d" stroke-width="4"/>
<path d="M240 150 L146.4 540 H333.6 Z" fill="#dcecf7" opacity="0.7" stroke="#6093ba" stroke-dasharray="7 5"/>
<rect x="224" y="126" width="32" height="24" rx="4" fill="#2879bc"/>
<path d="M135 126 H224 M256 126 H345" stroke="#47647d" stroke-width="5"/>
<path d="M240 150 V540" stroke="#8ea4b5" stroke-dasharray="4 4"/>
<path d="M135 189 H345" stroke="#f1b154" stroke-width="2"/>
<path d="M135 228 H345" stroke="#c45650" stroke-width="3"/>
<path d="M135 345 H345" stroke="#23865b" stroke-width="3"/>
<path d="M135 462 H345" stroke="#6093ba" stroke-width="2"/>
<text x="390" y="195" font-size="20">90% height → distance 13 cm</text>
<text x="390" y="234" font-size="20" font-weight="bold">80% height → 26 cm → FULL after 60 s</text>
<text x="390" y="351" font-size="20" font-weight="bold">50% height → 65 cm → CLEAR after 120 s</text>
<text x="390" y="468" font-size="20">20% height → distance 104 cm</text>
<text x="390" y="546" font-size="20">Empty → distance 130 cm</text>
<path d="M135 570 H345" stroke="#456179" stroke-width="2"/>
<text x="170" y="600" font-size="20">70 cm width</text>
<text x="40" y="642" class="small">Approximate 27° cone envelope at the bottom: 62.4 cm; only 3.8 cm nominal clearance per side.</text>
<text x="40" y="671" class="small">FoV is diagonal and target-dependent. Drawing assumes straight walls and a centered sensor.</text>
<text x="40" y="700" class="small">Measure actual H, bottom width and the other dimension. This estimates local height, not volume.</text>
</svg>'''
(ROOT/"bin-geometry.svg").write_text(geometry)

print(f"Generated {len(req_rows)} requirement test cases, engineering tables and three SVG diagrams.")
print(f"Nominal 27-degree cone envelope at1.3m: {2*1.3*math.tan(math.radians(27/2)):.3f}m")
