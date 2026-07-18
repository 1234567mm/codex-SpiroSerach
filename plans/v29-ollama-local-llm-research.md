# V29 Ollama 本地 LLM 论文组抽取调研

## 范围

本调研面向 SpiroSearch 的论文 PDF 组抽取：一组输入由正文 PDF 和补充信息 PDF/SI 组成，模型只用于从已解析文本中抽取候选事实，并把结果交给既有 provenance、review、quality gate 流程。模型不得直接输出推荐、排名、评分结论或实验决策。

当前仓库已有相关边界：

- `src/spirosearch/paper_ingest.py` 当前 `paper-ingest` 只接受 `extractor="regex"`，并按 paper group 同时解析 `main` 与 `si` 文档。
- `src/spirosearch/providers/llm_literature.py` 已有 LLM 文献 provider/extractor 合同：LLM 输出必须是对象，包含 `claims` 数组，claim 必须有 `raw_span`，且拒绝 `recommendation` 或 `decision`。
- 因此 V29 的合理接入点是新增本地 Ollama extractor/provider，复用现有 `LiteratureExtractionAgent` 与 review 队列，而不是把 LLM 放进评分层。

## 一手来源

- Ollama API 文档：https://docs.ollama.com/api
- Ollama structured outputs 文档：https://docs.ollama.com/capabilities/structured-outputs
- Ollama CLI 文档：https://docs.ollama.com/cli
- Ollama Windows 下载/安装说明：https://ollama.com/download/windows
- Ollama Qwen 3.5 模型页：https://ollama.com/library/qwen3.5
- Ollama Qwen3 模型页：https://ollama.com/library/qwen3
- Qwen3 官方说明：https://qwenlm.github.io/blog/qwen3/
- Ollama Gemma3 模型页：https://ollama.com/library/gemma3
- Google Gemma 3 model card：https://ai.google.dev/gemma/docs/core/model_card_3
- Ollama Llama 3.1 模型页：https://ollama.com/library/llama3.1
- Meta Llama 3.1 官方说明：https://ai.meta.com/blog/meta-llama-3-1/

## 推荐模型优先级

### P0：`qwen3.5:9b`

推荐作为第一试跑模型。理由：

- Ollama 当前模型库提供 `qwen3.5`，其中 `9b` 是质量和本地运行成本之间的首选折中；比 4B 更稳，比 27B/30B/32B/35B 更容易在普通工作站落地。
- Qwen 系列官方说明强调多语言、科学/数学/代码能力，以及 thinking/non-thinking 模式；对中英混合论文、表格标题、实验条件、材料缩写更友好。
- 部署路径简单，适合先验证 SpiroSearch 的 extractor 合同、JSON 约束、review 回退和可复现记录。

最低硬件假设：

- 建议 16 GB 系统内存起步；有 8 GB 以上显存更舒服。
- 无 GPU 也可 CPU 跑通流程，但批量 PDF 会慢，应先用 5-20 组论文做 schema 和 prompt 回归。
- 如果正文+SI 合并后过长，优先分 chunk 抽取，不依赖一次性塞完整论文。

### P1：`qwen3:8b`

推荐作为稳定回退模型。理由：

- 如果 `qwen3.5:9b` 在本机拉取、速度或结构化输出稳定性上不理想，`qwen3:8b` 仍是中英科学论文文本抽取的稳妥选择。
- 8B 级别仍然比 4B 更适合复杂 SI 表格、器件条件和材料缩写消歧。
- 对第一轮 20 组论文的质量评估来说，它可以作为可复现 baseline。

最低硬件假设：

- 建议 16 GB 系统内存起步；有 8 GB 以上显存更舒服。
- 无 GPU 也可 CPU 跑通流程，但批量 PDF 会慢，应先用 5-20 组论文做 schema 和 prompt 回归。

### P2：`qwen3.5:4b` 或 `qwen3:4b`

推荐作为低硬件 fallback。理由：

- 仍然保留 Qwen3 的中英多语言优势。
- 适合在 8-16 GB 内存机器上做 smoke test、prompt 迭代和离线开发。
- 风险是复杂 SI 表格、多器件条件、缩写消歧和跨段合并可能更不稳定，必须更依赖 `raw_span`、review queue 和人工复核。

最低硬件假设：

- 8-16 GB 系统内存可试跑。
- 更适合小 batch、短 chunk 和合同测试，不建议作为最终批量抽取唯一模型。

### P3：`gemma3:12b` 或 `gemma3:4b`

推荐作为第二路线和交叉复核模型。理由：

- Google Gemma 3 model card 标注其支持长上下文、多语言，并包含图像输入能力；Ollama 模型库也提供 Gemma3。
- 对 PDF 组抽取来说，第一阶段仍建议抽文本后使用文本输入；当 SI 中表格截图、图像化页面很多时，Gemma3 可作为后续视觉页抽取候选路线。
- 由于科学材料缩写、中英混合和化学/器件实体并非 Gemma 的唯一强项，建议用它补充或复核 Qwen3，而不是替代首选。

最低硬件假设：

- `gemma3:4b` 可作为低硬件备选。
- `gemma3:12b` 建议至少 24 GB 系统内存或有足够显存；批量处理前必须先测吞吐。

### P4：`llama3.1:8b`

推荐作为英文长文 baseline，不作为中英科学抽取首选。理由：

- Meta Llama 3.1 官方说明强调 128K 上下文与多语言能力，Ollama 模型库也提供 `llama3.1`。
- 对英文正文和 SI 的长上下文基线有价值。
- 对中文、材料缩写、单位归一、结构化 JSON 严格性，本项目仍应优先试 Qwen3。

最低硬件假设：

- 16 GB 系统内存起步。
- 更适合英文论文抽取对照实验和质量评估，不建议作为唯一默认模型。

## 为什么适合中英科学论文结构化抽取

论文组抽取的难点不是“生成摘要”，而是从正文和 SI 中稳定抽取可追溯事实：

- 实体：HTL/小分子/聚合物名称、perovskite 组成、器件结构、电极、添加剂。
- 指标：PCE、Voc、Jsc、FF、HOMO、LUMO、mobility、conductivity、stability、film/process 条件。
- 条件：champion/average、scan direction、illumination、area、dopant、solvent、annealing、measurement atmosphere。
- 证据：必须保留 `raw_span`、chunk/page/table/source，并能回到正文或 SI。

Qwen 3.5/3 是首选，因为它的一手说明覆盖多语言与科学/数学/代码类能力，而本项目的目标输出又是严格 JSON schema，不是自由文本。Gemma3 的价值在于长上下文和后续视觉页路线；Llama3.1 的价值在英文长文 baseline。

关键实现策略：

- 不把正文+SI 整组一次性喂给模型；按页面、段落、表格、caption、SI section 切 chunk。
- 每个 chunk 只抽取局部 claims；跨 chunk 合并由 deterministic 层完成。
- 对同一 paper group 维护 `group_id`，但 claim 仍记录来源是 `main` 还是 `si`。
- 对数值、单位、条件做 schema 约束；模型只给候选，系统做规范化和 review。

## JSON、温度、上下文和可复现设置

Ollama 官方 API 支持在请求中设置 `format`，包括 JSON schema；structured outputs 文档建议配合 schema 约束模型输出。因此本项目应使用 schema-first 请求，而不是靠 prompt 口头要求“请输出 JSON”。

建议参数：

- `temperature: 0`
- 固定 `top_p`、`top_k` 或使用默认值并记录完整 options；不要在同一评测批次混用。
- 固定 model tag，并记录 `ollama list` 中的模型名称、ID/digest、size、modified 时间。
- 固定 prompt version，例如 `spirosearch-v29-local-llm-extract-v1`。
- 固定 chunking 策略：chunk size、overlap、PDF parser 版本、是否 OCR、是否包含 SI。
- 固定输出 schema version，例如 `v29.local_llm_claim_candidate.v1`。

建议 JSON schema 字段：

```json
{
  "type": "object",
  "properties": {
    "claims": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "raw_span": { "type": "string" },
          "property_name": { "type": "string" },
          "value": { "type": ["number", "string"] },
          "unit": { "type": "string" },
          "material": { "type": ["string", "null"] },
          "method": { "type": ["string", "null"] },
          "conditions": { "type": "object" },
          "confidence": { "type": "number" }
        },
        "required": ["raw_span", "property_name", "value", "unit", "conditions"]
      }
    }
  },
  "required": ["claims"]
}
```

上下文长度建议：

- 不以模型最大 context 作为设计目标；即使模型支持长上下文，也优先 chunk 化。
- 单次请求建议控制在 4K-12K token 等级，先保证稳定 JSON 和 `raw_span` 命中率。
- 对 SI 表格可使用“表格行/表格块”为 chunk 单位；对正文可用 section/page/caption 为 chunk 单位。
- 长上下文只用于“同一 paper group 的上下文提示”，例如提供 title、DOI、材料别名表，而不是塞完整 PDF。

可复现产物建议记录：

- `model_name`
- `model_digest`
- `ollama_version`
- `prompt_version`
- `schema_version`
- `temperature`
- `options`
- `chunk_id`
- `document_id`
- `paper_group_id`
- `source_asset_sha256`
- `raw_response_sha256`
- `parsed_response_sha256`

## 当前项目接入建议

建议 V29 分三层接入：

1. `OllamaClient`：只负责调用本地 `http://127.0.0.1:11434/api/chat` 或 `/api/generate`，传入 schema、prompt、chunk 文本和 deterministic options。
2. `LocalLlmSchemaClaimExtractor`：实现与现有 `LlmSchemaClaimExtractor` 等价的合同，输出 claim candidates，拒绝无 `raw_span`、包含 `recommendation`/`decision`、非 JSON 或 schema 不合格输出。
3. `paper-ingest --extractor local-llm`：作为 `regex` 的并列 extractor，写入同样的 manifest-backed artifacts 和 review queue。

必须保持的边界：

- provider/extractor 只产生 evidence candidates，不产生推荐、评分、排序、admit/no-admit。
- LLM confidence 不能直接进入 scoring；最多作为 review 排序或机器抽取元数据。
- 所有 claim 必须有 `raw_span` 和来源定位；没有证据片段就进入 review/blocking。
- read-only viewer 或 artifact reader 不允许触发 Ollama live call。
- 正文+附件作为 paper group 输入，但 artifact 必须能区分 `main` 与 `si` 来源。

建议首批验收指标：

- JSON parse 成功率。
- schema 合格率。
- `raw_span` 可回查率。
- PCE/Voc/Jsc/FF 基础指标召回。
- SI 表格中条件字段召回。
- 错误进入 review queue 的比例。
- 与 regex extractor 的重叠和增量 claims。

## 命令示例

当前这台 Codex PowerShell 会话里执行 `ollama --version` 和 `ollama list` 均失败，错误是 PowerShell 找不到 `ollama` 命令。用户已说明 Ollama 已安装，因此更可能是 PATH 尚未刷新、安装后未重开终端、或 Ollama 安装路径没有加入当前 shell 环境。建议先重开 PowerShell/Codex 终端，或使用 Ollama 可执行文件完整路径确认。

常用 CLI：

```powershell
ollama --version
ollama list
ollama pull qwen3.5:9b
ollama run qwen3.5:9b
ollama serve
```

低硬件 fallback：

```powershell
ollama pull qwen3:8b
ollama pull qwen3.5:4b
ollama run qwen3:8b
```

Gemma3 复核路线：

```powershell
ollama pull gemma3:4b
ollama pull gemma3:12b
```

API smoke test：

```powershell
$body = @{
  model = "qwen3.5:9b"
  messages = @(
    @{
      role = "user"
      content = "Extract PCE claims from: The champion device achieved a PCE of 21.3%, Voc of 1.12 V, Jsc of 24.1 mA cm-2."
    }
  )
  stream = $false
  format = @{
    type = "object"
    properties = @{
      claims = @{
        type = "array"
        items = @{
          type = "object"
          properties = @{
            raw_span = @{ type = "string" }
            property_name = @{ type = "string" }
            value = @{ type = @("number", "string") }
            unit = @{ type = "string" }
            conditions = @{ type = "object" }
          }
          required = @("raw_span", "property_name", "value", "unit", "conditions")
        }
      }
    }
    required = @("claims")
  }
  options = @{
    temperature = 0
  }
} | ConvertTo-Json -Depth 20

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11434/api/chat" -ContentType "application/json" -Body $body
```

## 执行建议

第一轮不要追求最大数据量，先做 20 组论文的封闭评测：

1. 准备正文+SI paper group，确保每组有 DOI、license、main sha256、SI sha256。
2. 用现有 regex extractor 跑 baseline。
3. 用 `qwen3.5:9b` 跑 local-llm extractor；如果本机不稳定，再切到 `qwen3:8b`。
4. 对比 claim 增量、raw_span 命中、review queue 原因。
5. 再用 `qwen3.5:4b`、`qwen3:4b` 或 `gemma3:4b` 做同批次复核，判断低硬件模型是否够用。

若第一轮稳定，再进入 100-500 组批量抽取，并把模型输出与 NOMAD PSC/PERLA、HOPV15、OPV-DB 等公开数据源做交叉验证。数据丰富度应来自多源 provenance 合并，而不是让 LLM 自行补全缺失事实。

## 结论

- 默认推荐 `qwen3.5:9b`：最适合当前中英科学论文结构化抽取的本地起点。
- 稳定回退用 `qwen3:8b`；低硬件先用 `qwen3.5:4b` 或 `qwen3:4b` 跑通流程，但不要把 4B 当最终质量基线。
- `gemma3` 适合做第二模型复核，后续可探索视觉页/SI 表格截图。
- `llama3.1:8b` 可做英文长文 baseline，但不作为本项目首选。
- Ollama 必须以 schema-first、temperature 0、固定 prompt/model/chunking 的方式接入。
- 在 SpiroSearch 内只接入 provider/extractor 层；评分和决策仍由现有 evidence policy、review、scoring view 负责。
