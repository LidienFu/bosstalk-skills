---
name: reframe-eye
description: 橫式影片（16:9）轉直式（9:16 reels、shorts、抖音）之前，先逐個鏡頭看畫面、決定每一鏡要怎麼裁，避免人臉、字卡、產品被切掉。使用者要把橫的影片轉成直的、做 reels 或 shorts、或提到 ffmpeg-skill 的 fit.py 裁切時使用。需要已安裝 ffmpeg-skill。
---

# 轉直式前先看畫面（reframe-eye）

ffmpeg-skill 的 fit.py 預設從正中間裁，它自己看不懂畫面。這份說明書讓你（AI）先看過每一個鏡頭，替每一鏡決定裁切方式，再交給 ffmpeg-skill 執行。

## 準備

- ffmpeg-skill 的工具資料夾記為 `S`（通常是 `~/.claude/skills/ffmpeg-skill/scripts`）
- Windows 把 `python3` 換成 `py` 或 `python`
- 全程在使用者電腦上跑，影片不上傳
- 如果另外裝了 reframe-track（人臉追蹤），可以用在「追蹤」的鏡頭；沒裝就用模糊背景代替

## 步驟

1. **量尺寸**：`python3 $S/probe.py 原片.mp4 --compact`，記下寬 W、高 H。直式裁切框寬度 `cw = H × 9 ÷ 16`（1920×1080 的片是 608）。
2. **切鏡頭**：`python3 $S/scenes.py 原片.mp4 --json`，拿到每一鏡的開始和結束秒數。
3. **每一鏡抽三張圖**：開頭後 0.3 秒、中間、結束前 0.3 秒。
   `python3 $S/look.py 原片.mp4 --at 1.3 --at 4.0 --at 6.7 -o shot01`
   一定要自己打開圖片看，不能只看檔名或秒數猜。
4. **判斷每一鏡**，照下表選一種：

   | 畫面 | 處理 | 參數 |
   |---|---|---|
   | 一個人或一個產品，三張圖位置差不多 | 固定裁切 | `--fit crop --crop-x 數值` |
   | 主角在鏡頭裡明顯移動（三張圖位置差超過 cw 的四分之一） | 追蹤 | 有 reframe-track 就用它，沒有就模糊背景 |
   | 橫向的字卡、簡報、表格、字幕，或並排的兩個以上的人，寬度超過 cw | 模糊背景 | `--fit blur` |
   | 字或重點貼在畫面左右邊緣 | 模糊背景 | `--fit blur` |
   | 看不出主角（風景、空景） | 固定裁切置中，或模糊背景 | 看畫面決定 |

   crop-x 的算法：主角中心的 x 座標記為 `cx`，`crop-x = (cx − cw ÷ 2) ÷ (W − cw)`，小於 0 填 0，大於 1 填 1。人臉要留頭頂空間時，以眼睛位置當 cx 即可，不用上下調。

5. **先給使用者看計畫，不要直接剪**。用一張表列出：鏡頭、秒數、處理方式、crop-x、理由（一句話）。使用者說可以再做下一步。
6. **有裝 reframe-track 的話，走這條（最推薦）**：把計畫寫成 `plan.json`，一次輸出整支，聲音和嘴型不會跑掉。
   ```json
   {"shots": [
     {"start": 0, "end": 6.5, "mode": "crop", "crop_x": 0.18},
     {"start": 6.5, "end": 12.0, "mode": "track"},
     {"start": 12.0, "end": 20.0, "mode": "blur"}
   ]}
   ```
   `python reframe-track/scripts/track_reframe.py 原片.mp4 --plan plan.json -o 直式.mp4`（路徑換成你放 reframe-track 的位置），做完直接跳到第 8 步。

   **沒裝 reframe-track，逐鏡執行**（鏡頭很多的口說影片，接完要檢查最後一鏡的嘴型有沒有對上）：
   - 剪出這一鏡：`python3 $S/cut.py 原片.mp4 --start 開始 --end 結束 --accurate -o shot01.mp4`
   - 固定裁切：`python3 $S/fit.py shot01.mp4 --aspect 9:16 --fit crop --crop-x 0.18 -o shot01_v.mp4`
   - 模糊背景：`python3 $S/fit.py shot01.mp4 --aspect 9:16 --fit blur -o shot01_v.mp4`
   - 追蹤：沒有 reframe-track 就改用模糊背景
7. **接回去**：`python3 $S/join.py shot01_v.mp4 shot02_v.mp4 … --transition none --width 1080 --height 1920 -o 直式.mp4`
   接點的聲音容易有小斷點，接完用原片的聲音蓋回去：先 `python3 $S/audio.py 原片.mp4 -o 原音.wav`，再 `python3 $S/audio.py 直式.mp4 --replace 原音.wav -o 直式_原音.mp4`。
8. **匯出和檢查**（走 reframe-track 的話，把下面的 `直式_原音.mp4` 換成 `直式.mp4`）：
   - `python3 $S/export.py 直式_原音.mp4 --preset reels --normalize -o 完成.mp4`（`--normalize` 同時把音量調到 Reels 標準）
   - `python3 $S/check.py 完成.mp4 --platform reels`，有不合格的項目就照它給的指令修
9. **最後再看一次**：`python3 $S/look.py 完成.mp4 --safe reels`，打開圖片確認每一鏡的臉和字都在畫面裡、沒被平台按鈕和說明文字擋住。有被切到的鏡頭，回到第 4 步改參數重做。

## 回報格式

完成：檔名、長度、尺寸
每一鏡：處理方式和理由
看過的檢查圖：檔名
需要注意：例如「第 3 鏡主角走出畫面，改用模糊背景」

## 不要做

- 沒看圖就決定 crop-x
- 字卡硬裁成直的（字一定會被切掉）
- 沒經過使用者同意就覆蓋原片
