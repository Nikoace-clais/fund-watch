# fund-watch 路线图

> 制定日期：2026-07-07 · 基于代码库盘点 + 同类开源项目调研
> 目标形态（已确认）：**NAS/家庭自托管**，轻量多用户（家人账号），不做公网级安全加固
> 每期功能开工时按 SDD 工作流单独出 design 文档，本文只定方向与顺序。

---

## 一、现状判断

功能面已完整且无占位：基金池、盘中估值快照、多组合持仓 P&L、交易记录（含超卖校验）、OCR 导入（双模型核对）、AI 选基（SSE）、股票反查、大盘指数。代码健康度好：分层清晰、无散落 TODO、数据源有重试/TTL 缓存/降级、关键路径有测试。

### 四大地基缺口

| 缺口 | 证据 | 影响 |
|---|---|---|
| 无告警/提醒 | 后端无任何 alert/notify 代码，无 alerts 表 | 核心定位「低噪提醒」缺失 |
| 历史数据 30 天即删 | `snapshots.py::prune_old_snapshots(keep_days=30)`；历史净值不落库（每次现拉 + 10min TTL） | 回测/基准/归因/离线告警全被卡死 |
| 无生产部署形态 | 仅 start.sh 本地脚本，无 Docker/compose，CORS 硬编码 localhost | 无法 NAS 部署 |
| 无用户/认证 | 无 users 表、无 auth 中间件；AI/OCR 密钥前端 localStorage 携带 | 多人使用不可行 |

### 次级缺陷

- 快照调度器为进程内（lifespan），重启丢窗口、无补偿拉取
- 估值源 fundgz、详情源 eastmoney 单点无备源；缓存纯进程内，重启即失效
- `ai_agent.py`（630 行核心逻辑）无测试；风险指标阈值为硬编码启发式
- P&L 为成本法，无 XIRR/TTWR 真实收益率
- 前端：错误提示用 `window.alert()`；StockFunds/ImportPage 无响应式断点，宽表窄屏溢出

## 二、竞品对照

| 项目 | 形态 | 可借鉴点 | fund-watch 相对优势 |
|---|---|---|---|
| [leek-fund 韭菜盒子](https://github.com/LeekHub/leek-fund) | VSCode 插件 | 涨跌提醒、低打扰形态、轮询间隔可配 | 组合分析深度、OCR/AI |
| [Ghostfolio](https://github.com/ghostfolio/ghostfolio) | 自托管 Web（Docker） | Docker 自托管、PWA、多用户、再平衡 | A 股基金数据源适配、OCR 导入 |
| [Wealthfolio](https://wealthfolio.app/) | local-first + Docker | 基准比较、目标权重+漂移、蒙特卡洛模拟 | 盘中估值、中文生态 |
| [Portfolio Performance](https://www.portfolio-performance.info/en/) | Java 桌面 | TTWR/IRR 收益率算法 | 现代 Web UI、实时估值 |
| [VibeAlpha Terminal](https://github.com/Austin-Patrician/eastmoney) | A 股 AI 分析平台 | AI 盘前/盘后报告、AI 组合诊断 | 更完整的持仓/交易闭环 |
| real-time-fund / 基金宝 等 | 纯前端小工具 | —（已全面超越） | 持久化、后端、AI |
| Magpie / PanWatch | 价格告警工具 | Server酱/Bark 推送模式 | — |

**结论**：「A 股基金 + 盘中估值 + AI/OCR」细分无直接对手；差距集中在数据底座、告警、部署形态、收益率算法这些通用能力上。

## 三、路线图

### 短期（0-2 个月）——补地基，交付提醒

1. [ ] **历史数据底座**：新增 `fund_nav_history` 表（日频净值落库，增量拉取）；快照保留分层（盘中 5min 粒度保 30 天，收盘快照永久保留）。告警/基准/回测的共同前置，最先做。
2. [ ] **提醒规则 MVP**：`alerts` 表（阈值 + 冷却时间 + 静默时段）；挂在现有 snapshot_scheduler 拉取后评估；推送通道首发 **Server酱（微信）**，通道层留最小抽象以便后续加 Bark/Telegram；前端告警管理页。
3. [ ] **调度健壮化**：启动时 catch-up 补拉、pull_quotes.py + crontab 配置文档化、失败重试记录。
4. [ ] **体验小修**：`window.alert()` → toast 组件；StockFunds/Portfolio 宽表移动端溢出修复。
5. [ ] **测试补齐**：ai_agent.py 核心路径、snapshot 调度时段判断单测。

### 中期（2-6 个月）——从「看板」到「NAS 自托管分析工具」

6. [ ] **Docker 化**：Dockerfile + compose（backend + 前端静态产物），CORS/端口环境变量化，NAS 一键部署。
7. [ ] **基准比较**：组合/单基金 vs 沪深300、中证500、偏股混合基金指数（依赖 #1 净值库）。
8. [ ] **收益率算法升级**：XIRR（资金加权）+ TTWR（时间加权）。
9. [ ] **目标配置与漂移**：设定目标资产配置，偏离超阈值时提醒（复用 #2 告警通道）。
10. [ ] **数据源备源**：估值/净值加第二数据源 fallback（腾讯/akshare 系），消除单点。
11. [ ] **PWA**：manifest + service worker，移动端安装 + Web Push（复用告警）。

### 长期（6-12 个月）——多人可用 + 智能深化

12. [ ] **轻量用户维度**：简单认证（本地账号密码，无需 OAuth）+ users 表 + portfolios.user_id；funds/快照/行业缓存保持全局共享；AI/OCR 密钥服务端加密存储；SQLite+WAL 足够家庭并发，不迁 Postgres。
13. [ ] **分享**：组合只读分享链接（脱敏金额可选）。
14. [ ] **AI 深化**：定期 AI 组合诊断/收盘日报推送；风险指标阈值用积累的历史数据校准（替换启发式）。
15. [ ] **定投回测与模拟**：基于净值库的定投回测、简单蒙特卡洛。

### 明确不做（YAGNI）

- 实时 tick 级行情、自动交易/下单
- 全市场数据爬取入库（只存自选相关）
- 多资产大而全（股票/债券/房产记账）——守住「A 股基金盯盘」定位
- 移动原生 App（PWA 覆盖）
