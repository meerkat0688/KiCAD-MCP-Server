# 垃圾桶滿載監視器 初步設計

日期：2026-11-17，Asia/Taipei。階段：v0.3 KiCad 載板草案完成，待備料及實體驗證；未完成產品驗收。

最新交付：[KiCad 專案](kicad/bin_monitor_carrier.kicad_pro)、[原理圖](kicad/bin_monitor_carrier.kicad_sch)、[PCB](kicad/bin_monitor_carrier.kicad_pcb) 及 [載板說明](kicad/README.md)。使用者後續明示可先進入電路與 PCB 設計；原始附件仍保留，範圍變更記錄於 requirements-update.md。

依使用者補充，桶高 **130 cm**、桶寬 **70 cm**、**無蓋**、硬體預算 **低於 US$50**。先以 Seeed Studio XIAO ESP32C3 與 Pololu 3415（VL53L1X）進行有線供電、Wi-Fi、單點高度原型。感測面至桶底的有效 H 必須安裝後校正；130 cm 是目前計算用假設，不是量測結果。

資料路徑：VL53L1X → I²C → XIAO ESP32C3 → HTTPS → 持久化通知服務 → LINE Messaging API → 指定群組。LINE 憑證只放在後端。

| 項目 | 初步結果 |
|---|---|
| 滿載門檻 | H=130 cm 時，d≤26 cm 持續 60 秒 |
| 清空門檻 | H=130 cm 時，d≥65 cm 持續 120 秒 |
| 取樣 | 每 5 秒；最近 3 筆有效值中位數；無效值立即中斷持續計時 |
| 主要兩模組價格 | US$27.85，官方網頁單件標價；不含稅運 |
| 硬體成本 | 原模組原型估 US$43.85 不含新增載板；載板版總價待報價，成本驗收 BLOCKED |
| 狀態介面 | USB 本機診斷及載板 GPIO4 LED 電路；韌體尚待實作，充電燈不代表應用狀態 |
| 客製 PCB | 已建立 50×38 mm、2 層載板草案；不作製造放行 |
| 備料 | 使用者確認兩個模組均尚未持有 |

直接閱讀 [architecture.md](architecture.md)、[prototype-wiring.svg](prototype-wiring.svg)、[bin-geometry.svg](bin-geometry.svg) 與 [system-overview.svg](system-overview.svg)。完整介面列在 [interface-table.csv](interface-table.csv)，成本列在 [bom.csv](bom.csv) 及 [cost-budget.csv](cost-budget.csv)。

[requirements.md](requirements.md) 是原附件的未修改副本；[requirements-update.md](requirements-update.md) 記錄使用者的尺寸／預算變更及另提的實作決策，未默默改寫原契約。其餘交付物：

- [sensor-comparison.md](sensor-comparison.md)：感測範圍、精度及視野風險。
- [firmware-backend.md](firmware-backend.md)：狀態、持久化、重試與過期取消協定。
- [prototype-plan.md](prototype-plan.md)：最少元件實測順序。
- [test-plan.md](test-plan.md) 及 [traceability.csv](traceability.csv)：逐項需求驗收。
- [review-signoff.md](review-signoff.md)：未決項、負責角色與停止點。
- [references/sources.csv](references/sources.csv)：官方資料及查閱日期。
- [reference-model/](reference-model/)：離線偵測邏輯模型及測試，非可燒錄韌體。

先驗證 130 cm 空桶、104/65/26/13 cm 平面靶，以及黑色袋裝垃圾。VL53L1X 的宣傳最遠距離不能視為現場量程保證。尤其空桶底部、日照及窄 ROI 可能縮短量程。

所有實體、網路及 LINE 驗收目前 NOT RUN；缺少必要設備／配置的項目在追溯表標為 BLOCKED。軟體模型測試另外記錄，不取代任何實體驗收。載板的實際 ERC／DRC／原理圖一致性與 netlist 靜態檢查見 [validation.json](kicad/review/validation.json)。未採購、未部署後端、未發送通知、未輸出製造檔。
