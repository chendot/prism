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

hierarchical_framework：
- 用于系统、框架、组织或能力体系中的父子包含关系。
- 图是给人脑使用的认知界面，不是模块清单；控制同时竞争注意力的视觉组块，而不是机械限制 node 数。
- hierarchy_view=overview 时只画 3 到 7 个同粒度板块；每个板块恰好一个 primary 主判断，可带 0 到 2 个 secondary 或 muted 辅助要点。更深细节写入 omitted_details，另做 detail 子图。
- 节点密度随 target_format 调整：wechat_cover 建议 3–5，x_card 建议 3–6，xiaohongshu_card 建议 5–12，xiaohongshu_carousel 建议 8–20；这不是 schema 硬限制。
- hierarchy_view=detail 时只展开 focus_group 的一个认知问题，其他层折叠成边界或省略。
- abstraction_level 必须明确所有框共同的抽象海拔；不得把业务能力、技术组件和具体中间件放在同一张图。
- 同层节点使用一致的命名语法和粒度，例如全部是名词能力或全部是技术组件。
- diagram.groups 表达容器层级，node.group 表达组件归属；不要用 edge 模拟 contains。
- 每个节点必须属于一个 group，group.parent 只能引用另一个已声明 group。
- group 嵌套深度为 2 到 3 层，group 数量建议 2 到 8 个。
- 整体/局部与父子关系只用 group 空间包含表达，不创建 contains edge。
- group.order 是依赖顺序：只允许 TD，从上到下；跨 group edge 只能连接同一 parent 下相邻的下一层，禁止向上、反向和跨层跳跃。
- 同组节点由水平对齐表达同类关系，edge 不参与同组节点的 rank 计算。
- edge 只保留关键接口、调用、数据流或真实依赖；数量根据视觉组块和目标画布判断，不设置统一硬上限。
- 同组内能由位置理解的关系可以不画 edge，避免把层级架构图画成流程图。
- 颜色只编码 2 到 3 个稳定语义类别；同色必须同类，不使用装饰性彩虹配色。
- omitted_details 必须记录本图主动不画的实现细节，省略是 Story 判断而不是生成遗漏。
- 超出目标画布的建议密度时，优先拆成 overview 与 detail 子图；只有结构和方向错误才应阻止生成。
