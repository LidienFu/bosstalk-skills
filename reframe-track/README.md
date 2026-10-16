# reframe-track：跟著人臉轉直式

reframe-eye（純文字 skill）的第二層。橫的影片轉 9:16 時，裁切框會跟著人臉或人移動，也能照 reframe-eye 的逐鏡計畫一次輸出。

全部在本機跑：MediaPipe 偵測人臉、人；ffmpeg 輸出。影片不上傳。

## 安裝（一次就好）

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python scripts/get_models.py                # 下載兩個 Google 官方模型到 models/
```
電腦要有 ffmpeg。

## 用法

```bash
python scripts/track_reframe.py 原片.mp4 -o 直式.mp4                     # 自動：逐鏡判斷 跟拍／固定／模糊背景
python scripts/track_reframe.py 原片.mp4 --plan-only -o 報告.json        # 只分析，不輸出影片
python scripts/track_reframe.py 原片.mp4 --plan plan.json -o 直式.mp4    # 照 reframe-eye 的計畫輸出
python scripts/track_reframe.py 原片.mp4 -o 直式.mp4 --debug 檢查.mp4    # 另存一支畫出偵測框和裁切框的橫式檢查片
```

常用參數：`--subject face|person|auto`、`--smooth 0.6`（秒，越大鏡頭越穩）、`--deadzone 0.06`（主角小晃動時鏡頭不動）、`--lead 0.1`（主角走路時前方多留空間）。

## 限制

- 一個畫面同時有好幾個人時，跟最大、最靠近上一格位置的那個
- 偵測率低於 30% 的鏡頭自動改模糊背景，不硬裁
- 不認字：字卡、簡報請交給 reframe-eye 判斷成模糊背景
