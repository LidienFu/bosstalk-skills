---
name: reframe-track
description: 橫式影片轉直式時，讓裁切框跟著人臉或走動的人移動，偵測不到人的鏡頭自動改模糊背景。使用者要把有人物走動的橫式影片轉成 reels、shorts，或 reframe-eye 的計畫裡有「追蹤」的鏡頭時使用。需要 Python、ffmpeg 和 MediaPipe。
---

# 跟著人轉直式（reframe-track）

reframe-eye 的第二層。reframe-eye 負責看畫面、決定每一鏡怎麼裁；這裡的程式負責「跟拍」：在使用者電腦上用 MediaPipe（Google 開源）抓人臉，抓不到臉就抓人，裁切框跟著移動。影片不上傳。

程式在 `scripts/`，做什麼都寫在下面，使用前可以逐行看過。

## 第一次使用：安裝

在這個資料夾裡執行（Windows 把 `.venv/bin/python` 換成 `.venv\Scripts\python`）：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/get_models.py
```

`get_models.py` 只會從 Google 官方的 MediaPipe 模型網址下載兩個檔案（人臉偵測、人物偵測）到 `models/`。安裝前先告訴使用者會裝哪些套件、下載哪些檔案，使用者同意才裝。

## 用法

```bash
# 自動：逐鏡判斷 跟拍／固定裁／模糊背景
.venv/bin/python scripts/track_reframe.py 原片.mp4 -o 直式.mp4

# 只分析不輸出：看每一鏡的偵測率和建議處理方式
.venv/bin/python scripts/track_reframe.py 原片.mp4 --plan-only -o 報告.json

# 照 reframe-eye 的計畫一次輸出（聲音和嘴型不會跑掉）
.venv/bin/python scripts/track_reframe.py 原片.mp4 --plan plan.json -o 直式.mp4

# 另存一支檢查片：橫式原片上畫出偵測到的主體和裁切框
.venv/bin/python scripts/track_reframe.py 原片.mp4 -o 直式.mp4 --debug 檢查.mp4
```

常用參數：
- `--subject face|person|auto`：只抓臉、只抓人，或先臉後人（預設）
- `--smooth 0.6`：鏡頭平滑程度（秒），越大越穩
- `--deadzone 0.06`：主角小晃動時鏡頭不動
- `--width 1080 --height 1920`：輸出尺寸；原片解析度低時改成原尺寸（例如 720p 原片用 `--width 406 --height 720`），不要硬放大

## 做完一定要看

1. 看輸出的 JSON：每一鏡的 `mode`（track 跟拍／crop 固定／blur 模糊背景）和 `detect_rate`
2. 用 `--debug` 的檢查片或 ffmpeg-skill 的 `look.py` 抽圖，親眼確認主角在框裡
3. 偵測率低於 30% 的鏡頭已自動改模糊背景，回報時要說明

## 限制（回報時照實說）

- 同一個畫面好幾個人時，只跟最大、最接近上一格位置的那個
- 不認字：字卡、簡報交給 reframe-eye 判斷成模糊背景
- 人背對鏡頭或很小時，可能抓不到，會改模糊背景
