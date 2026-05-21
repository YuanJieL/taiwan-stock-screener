# 台股三大法人選股篩選器 🔍

每個交易日收盤後自動執行，篩選出同時符合以下兩個條件的台股個股：

| 條件 | 說明 |
|------|------|
| **三大法人淨買超占比 > 10%** | 當日三大法人淨買量 ÷ 當日總成交量 |
| **近20交易日漲幅 > 30%** | 以當日收盤價 vs 20個交易日前收盤價計算 |

---

## 📊 線上網頁

啟用 GitHub Pages 後可直接訪問：

```
https://<你的帳號>.github.io/<repo名稱>/
```

---

## 🗂 專案結構

```
taiwan-stock-screener/
├── .github/
│   └── workflows/
│       └── daily_screener.yml   # GitHub Actions 排程
├── scripts/
│   ├── screener.py              # 主篩選邏輯（抓 TWSE API）
│   └── build_html.py            # 從 JSON 產生 HTML
├── data/
│   └── latest.json              # 每日自動更新的篩選結果
├── docs/
│   └── index.html               # GitHub Pages 靜態網頁
├── requirements.txt
└── README.md
```

---

## 🚀 快速部署步驟

### 1. Fork / Clone 此 Repo

```bash
git clone https://github.com/<你的帳號>/taiwan-stock-screener.git
cd taiwan-stock-screener
```

### 2. 啟用 GitHub Pages

1. 進入 repo → **Settings → Pages**
2. Source 選 **`Deploy from a branch`**
3. Branch 選 **`main`**，資料夾選 **`/docs`**
4. 按 **Save**

### 3. 確認 Actions 有寫入權限

1. 進入 **Settings → Actions → General**
2. 往下找 **Workflow permissions**
3. 選 **Read and write permissions** → Save

### 4. 手動觸發一次測試

1. 進入 **Actions** 頁面
2. 選左側 **每日台股法人選股更新**
3. 右側點 **Run workflow** → **Run workflow**

完成後 `data/latest.json` 與 `docs/index.html` 會自動 commit 進 repo，網頁也會更新。

---

## ⏰ 自動排程時間

GitHub Actions cron 設定為 **UTC 10:00（台北時間 18:00）**，僅週一至週五執行（對應台股交易日）。

---

## 🛠 本地端手動執行

```bash
pip install -r requirements.txt

# 執行今日篩選
python scripts/screener.py

# 也可指定日期（格式 YYYYMMDD）
python scripts/screener.py 20260521

# 產生 HTML
python scripts/build_html.py
```

---

## 📡 資料來源

- [TWSE 三大法人買賣超日報 T86](https://www.twse.com.tw/zh/trading/foreign/t86.html)
- [TWSE 每日收盤行情 MI_INDEX3](https://www.twse.com.tw/zh/trading/historical/mi-index.html)
- [TWSE 個股月成交資訊 STOCK_DAY](https://www.twse.com.tw/zh/trading/historical/stock-day.html)

---

## ⚠️ 免責聲明

本工具篩選結果僅供參考，**不構成任何投資建議**。股市投資有風險，請自行評估並承擔相關風險。
