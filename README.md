# Kindle 天气看板（GitHub Actions + GitHub Pages）

每小时由 GitHub Actions 生成一张 1448x1072 的横屏灰度 PNG，适配 Kindle Paperwhite 3 横屏分辨率，并发布 `api/display` JSON（KOReader 刷新间隔也设为 1 小时），
供 KOReader 的 TRMNL 插件（Base URL 指向你的 Pages 地址）拉取。天气数据来自 Open-Meteo，无需 API Key。

页面包含当前天气、未来 24 小时温度与降水概率、未来降雨概率最高的时段，以及当天日出和日落时间。
页面会按配置时区的日出、日落时间自动切换配色：日出至日落为白底黑字，日落至次日日出为黑底白字。

- 改城市、时区、刷新间隔：编辑 `config.json`
- 本地预览布局：`python generate.py --demo`（需要 Pillow 和 Noto Sans CJK 字体）
