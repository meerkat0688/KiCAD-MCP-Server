# 離線偵測模型

detector.py 是標準函式庫 Python 模型，不是 ESP32 韌體。它沒有硬體驅動、NVS、網路、LINE 或通知排程，不能據此宣稱對應實體需求 PASS。輸入 valid 必須由真正驅動的量測 status 決定；40–4000 mm 只是候選名義包絡，不保證實際量程。

在 repository 根目錄執行：

```bash
python3 -m unittest discover -s designs/bin-monitor/reference-model -v
python3 designs/bin-monitor/validate_design.py
```

測試涵蓋 60/120 秒邊界、中位數暖機、20 次短遮擋、2 小時滿載單事件、遲滯、無效值重置、30 秒獨立 watchdog、排程遺失、故障保留鎖存，以及 JSON snapshot 恢復。snapshot 僅示範哪些欄位應保留，不實作 flash 原子性或掉電安全。reboot 恢復及通知補送須另實作 DP-03 驗證。

三個保守提案：無效後清視窗（DP-01）；間隔>7.5秒重新建立連續性（DP-07）；故障不清 FULL 事件（DP-02）。不使用系統 wall clock 計算連續條件。測試發出的是記憶體中的 transition，沒有訊息副作用。
