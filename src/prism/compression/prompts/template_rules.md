模板是解释结构先验，不是视觉样式。你必须让输出符合当前模板，但最终 YAML 仍只能使用 Prism schema 和 ontology 词表。

所有模板共用的节点标题规则：
- `label` 优先写成一行可读的短标题；不要为了塞入解释而拉长标题。
- 信息较多时，把限定条件、示例和数字放进 `sublabel`，允许它换行。
- Renderer 会在安全上限内为较长标题加宽节点；超过上限才允许标题换行，不能依赖人为插入换行符。

value_flow：
- 用于利益分配、资金流、权力转移、DeFi 或稳定币机制。
- 必须有清晰参与方、价值/资金流向、收益归属或成本承担。
- 在 financial ontology 中，参与方通常映射为 issuer、buyer、regulator、intermediary、market；价值流优先映射为 fund_flow、issuance、authorization。
- primary 节点是核心利益分配矛盾点，且 primary 总数不超过 2；背景参与方和边缘约束方使用 muted。
- 推荐 8 到 14 个节点。

causal_chain：
- 用于风险传导、市场周期、政策影响、因果链。
- 节点按因果顺序排列，必须有明确触发点和结果节点。
- 边以 causal 为主，可用 information、fund_flow、feedback 表达预期、资金再配置和反馈。
- 必须至少包含一个 loop。
- primary 节点放在传导链的起点和终点，且 primary 总数不超过 2；背景性参与方使用 muted。
- 推荐 8 到 16 个节点。

layer_stack：
- 用于系统分层、软件架构、能力栈、流程分层。
- 节点必须带 layer 整数，按层级组织。
- 边只跨层连接，避免同层节点直接相连。
- 在不支持 depends_on/abstracts/enables 的 ontology 中，选择最接近的合法 edge.type。
- 推荐 6 到 12 个节点。
