# Fund Watch Plan (A股公募 · 免费数据源)

## 目标
构建一个可给多人使用的基金涨跌监控系统（先免费数据源），支持：
1. 实时估算净值拉取（天天基金 fundgz）
2. OCR 识别基金编号（6位代码）
3. 基金池持久化 + 估值快照持久化（SQLite）
4. 低打扰提醒（后续扩展）

## 数据源策略（V1）
- 实时估值：`https://fundgz.1234567.com.cn/js/{code}.js`
- 历史/基础信息：`https://fund.eastmoney.com/pingzhongdata/{code}.js`
- OCR：本地 OCR（RapidOCR ONNX）+ 正则提取 6 位代码

## 里程碑

### M1 - 可运行后端（今天）
- FastAPI 项目骨架
- SQLite 建表（funds / fund_snapshots / ocr_records）
- 基金增删查 + 实时估值抓取接口
- OCR 上传识别接口（返回候选代码并落库）

### M2 - 前端基础页面（下一步）
- 基金池列表页
- OCR 上传页
- 估值看板页（今日涨跌）

### M3 - 运营能力
- 定时拉取估值快照（cron）
- 组合级涨跌统计
- 分享页 + 读权限

## 持久化策略
- `funds`: 用户关注基金池
- `fund_snapshots`: 估值快照（用于趋势图与提醒阈值）
- `ocr_records`: OCR 原文、命中代码、时间、来源图像路径

## 风险与说明
- 免费源稳定性和字段可能波动，需要做降级和重试
- 估算净值不等于最终成交净值，前端需明确风险提示
- OCR 有误识别概率，入池前需人工确认
