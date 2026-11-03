# Kindle 天气看板（GitHub Actions + GitHub Pages）

每小时由 GitHub Actions 生成一张 1072x1448 的灰度 PNG，并发布 `api/display` JSON，
供 KOReader 的 TRMNL 插件（Base URL 指向你的 Pages 地址）拉取。天气数据来自 Open-Meteo，无需 API Key。

- 改城市、时区、刷新间隔：编辑 `config.json`
- 本地预览布局：`python generate.py --demo`（需要 Pillow 和 Noto Sans CJK 字体）
