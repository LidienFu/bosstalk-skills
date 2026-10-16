# 啾一下 AI 免費 Skills

啾一下 AI 在影片裡做過的 skill，都放在這裡，免費下載、免費改。

Skill 就是一個資料夾，裡面一份 SKILL.md 說明書。寫一次，**Claude 和 Gemini 都能用**。

## 有哪些

| Skill | 做什麼 | 下載 |
|---|---|---|
| [weekly-report](weekly-report/SKILL.md) | 把一週的零散筆記整理成固定格式的週報，沒寫清楚的列在「待確認」 | [weekly-report.zip](https://github.com/peakstargroup/chiuchiu-skills/releases/latest/download/weekly-report.zip) |
| [reframe-eye](reframe-eye/SKILL.md) | 橫的影片轉直式前，讓 AI 先看每個鏡頭、決定怎麼裁，人臉和字卡不被切掉（搭配 ffmpeg-skill） | [reframe-eye.zip](https://github.com/peakstargroup/chiuchiu-skills/releases/latest/download/reframe-eye.zip) |
| [reframe-track](reframe-track/SKILL.md) | 裁切框跟著人臉或走動的人移動（選配程式，在你電腦上跑 MediaPipe） | [reframe-track.zip](https://github.com/peakstargroup/chiuchiu-skills/releases/latest/download/reframe-track.zip) |

reframe-eye 和 reframe-track 要在你自己的電腦上處理影片，請在 Claude Code、Cursor 或 Codex 裡使用（Claude Code 解壓到 `~/.claude/skills/`），也要先裝好 [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill)。claude.ai 和 Gemini 網頁版用不了這兩個。

## 下載之前，先看內容

點上面表格的 skill 名稱，就能直接在網頁上讀完整的 SKILL.md。

網路上別人分享的 skill，裡面可能藏了會執行的程式。Anthropic 官方建議只裝自己做的、或官方提供的 skill，別人的先打開看過再裝。這裡的每個 skill 和選配的程式碼都開源：說明書是純文字，需要程式的 skill 會把程式放在獨立資料夾、寫清楚做什麼，不用也能照說明書使用。下載前都可以在網頁上逐行看過。

## 放進 Claude

1. 到 claude.ai 的設定，在「功能」這一頁把程式碼執行打開
2. 點左邊的 Skills，按右上角的「新增」，選「上傳」
3. 選下載好的 zip，確認名字和說明，按「上傳」

用的時候在對話裡打 `/` 選 skill，或直接說「幫我整理週報」，Claude 會自己判斷要不要用。

## 放進 Gemini

1. 打開 [Gemini 網頁版](https://gemini.google.com)，點左邊的「自訂」，切到「技能」
2. 按「建立」，選「上傳」，選同一個 zip
3. 確認內容後按「建立」

用的時候在對話裡打 `@` 選 skill。

Gemini 的 skills 從 2026 年 10 月 13 日開始分批開放，目前只有滿 18 歲的個人 Google 帳號能用，公司和學校帳號還要再等。

## 想改成自己的

下載 zip 解壓縮，用記事本打開 SKILL.md 改步驟和範例就好。改完記得：

- 資料夾名字要跟 SKILL.md 裡的 `name` 一樣
- `name` 只用小寫英文、數字和連字號，不要有 `claude` 這個字
- `description` 控制在 200 個字元以內，寫清楚「做什麼」和「什麼時候用」

照這三條，Claude 和 Gemini 都會收。

## 授權

[MIT](LICENSE)：可以免費使用、修改、分享，保留出處就好。

---

本專區由 啾一下 AI 維護，內容經真人查證。啾一下 AI 在 YouTube、Instagram、Threads、Facebook。
