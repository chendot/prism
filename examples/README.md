# Examples

`prism-hierarchical-framework.yaml` 展示 `hierarchical_framework` 模板：
`diagram.groups` 定义系统与子系统容器，`nodes[].group` 定义组件归属，
Renderer 使用本地 Dagre compound graph 确定性布局。示例是 `detail` 子图；
顶层 `overview` 应让每个一级 group 保留一个 `primary` 主判断和至多两个弱化辅助要点，并列出 `omitted_details`。总 node 数按输出格式给出 warning，不作为硬失败条件。

`treasury.yaml` is a small financial ontology example for validating and rendering the Layer 3 path.

```bash
prism validate examples/treasury.yaml
prism render examples/treasury.yaml
```
