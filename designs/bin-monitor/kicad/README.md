# 垃圾桶監視器 KiCad 載板草案

v0.3 DRAFT，2026-11-17。依使用者後續指示，先完成可編輯電路與 PCB；兩個模組目前均未持有，所有實物驗收仍未執行。

直接以 KiCad 10 開啟 [bin_monitor_carrier.kicad_pro](bin_monitor_carrier.kicad_pro)，再進入 [原理圖](bin_monitor_carrier.kicad_sch) 或 [PCB](bin_monitor_carrier.kicad_pcb)。保持整個資料夾一起移動，專案內的 BinMonitor.kicad_sym、BinMonitor.pretty 及相對 library tables 供應自訂元件。

| 項目 | 本版設計 |
|---|---|
| 板外形 | 50 × 38 mm、四角 R2、厚度 1.6 mm |
| 銅層 | 2 層；底層 GND pour；I²C 分層避交叉 |
| 固定 | 四個 2.2 mm NPTH、M2；每孔保留 5 mm 螺絲頭銅箔禁佈範圍 |
| 控制器 A1 | XIAO ESP32C3，使用兩列 7-pin 排針；USB 朝左邊緣；天線在模組上，載板沒有 RF 走線 |
| 感測器 | Pololu 3415 在板外，短線接 J1；本板不含裸 ToF 感測 IC |
| 供電 | 只由 XIAO USB-C 輸入 5 V；載板從模組取得 3.3 V；不接電池或第二電源 |
| J1 | JST XH 2.5 mm：1=3V3、2=GND、3=SDA、4=SCL |
| 狀態 LED | D2 / GPIO4 / A1 pad3 → 1k R1 → D1 anode；D1 cathode 接 GND，active high；韌體尚待實作 |
| 去耦 | J1 附近 10 µF / 10 V 0805 與 100 nF / 16 V 0603 |
| 測點 | TP1=3V3、TP2=GND、TP3=SDA、TP4=SCL；銅箔測點與孔不列採購 BOM |
| 初始設計規則 | 0.2 mm 間距、0.25 mm 訊號、0.5 mm 電源、0.6/0.3 mm via |

J1 的編號是本載板介面，不等於 Pololu 接腳由左到右的編號。感測模組端必須按 **VIN / GND / SDA / SCL 絲印**接線。VIN 維持 3.3 V，carrier I²C pull-up 會隨 VIN 改變；不可改接 5 V 後仍直連 ESP32。初版線長目標≤20 cm、100 kHz，這是設計假設，須量波形。XSHUT、GPIO1、VDD 初版不接線。

板上不額外增加 I²C 上拉，使用指定 Pololu carrier 的既有上拉。禁止以外觀相似的無位準轉換裸模組直接替換。這版沒有可宣稱通過的外接埠 ESD／長線防護驗證。

## 靜態檢查與預覽

[review/validation.json](review/validation.json) 記錄實際 KiCad 10.0.8 檢查：ERC 0、DRC 0、未佈線 0、原理圖一致性問題 0；另以匯出的 netlist 核對 21 個必要接點。使用 `--severity-all`，未以排除違規取得結果。原始報告為 [erc.json](review/erc.json) 與 [drc.json](review/drc.json)，並保存設計檔 SHA-256。

預覽：[原理圖 PNG](review/schematic.png)、[PCB 正面 PNG](review/pcb-top.png)、[PCB 背面 PNG](review/pcb-bottom.png)。正面圖不含底層走線，SCL 與部分電源線要在背面或 KiCad 層面板中查看。預覽不是製造檔。

ERC／DRC 不能證明 130 cm 感測、Wi-Fi、LINE、電源、接頭或機構通過。先前 US$43.85 是不含客製載板的模組原型規劃；新增 PCB、接頭、LED、電阻電容及組裝尚未報價，目前不能宣稱整套低於 US$50。

## 庫來源與裝配限制

模組符號與接腳中心來自 Seeed 官方 XIAO symbol／DIP footprint archives。專案衍生版本僅保留 14 個外圍接點，不使用底面電池與 JTAG 接點；排針孔改為 1.0 mm、焊盤 1.9 mm，仍須用實際排針尺寸及容差確認。保留極性方焊盤 1。刪除 vendor 封裝中不相干／非可攜的 3D model 路徑，重新安排絲印，未宣稱有經核對的 3D 組裝模型。

XIAO 以排針架高，不能把這個 THT 介面誤作直接 castellated SMD 安裝。需在 1:1 圖及實物上核對 USB 插拔、排針間距、高度、天線與固定支架。載板尺寸是為第一版評估選定，尚未由桶體安裝照片定版。Sensor 用獨立固定架朝下，不能只把本板貼在桶緣就假設光路正確。

Seeed 來源、下載 SHA-256、衍生修改及 KiCad 標準封裝副本列於 [library-provenance.json](library-provenance.json)。來源元件庫保存在 vendor-source/。新增零件的 Manufacturer、MPN 和 Datasheet 已寫入原理圖；完整裝置含板外模組的清單見 [../bom.csv](../bom.csv)。

## 重現

在 repository 根目錄、目標原理圖與 PCB 均未於 GUI 開啟時：

```bash
PYTHONNOUSERSITE=1 venv/bin/python designs/bin-monitor/kicad/prepare_libraries.py
PYTHONNOUSERSITE=1 venv/bin/python designs/bin-monitor/kicad/layout_board.py
python3 designs/bin-monitor/kicad/verify_kicad.py
```

layout_board.py 從 MCP 已由原理圖同步的 `.unrouted.kicad_pcb` 產生佈局；它會覆寫本版生成板，勿用來覆蓋手動修改。verify_kicad.py 執行 refill／save 與檢查，也應在 GUI 未持有目標檔時執行。上述腳本路徑適用目前這台 Mac。沒有輸出 Gerber、drill、貼片座標或製造 BOM；沒有採購、送板或製造放行。
