# LarkBridge

把“会后信息回填文档”做成一个可复用的 Lark/Codex skill。

这个仓库的目标不是直接改正文，而是把会议里的决策、待确认项、风险、行动项和范围变更，以评论的方式同步回飞书文档。它适用于 PRD，也适用于方案文档、SOP、项目计划、复盘文档，或者任何“先有初始文档，再通过会议逐步补齐”的场景。

AI 推理由 Codex 完成，仓库里的 Python 脚本负责做确定性工作：抓取文档、整理会议材料、抽取文档结构、生成评论计划草稿，以及在确认后把评论写回飞书文档。

## MVP 范围

- 目标文档优先支持 `docx`，因为它既支持全文评论，也支持局部评论。
- 旧版 `doc` 目前只适合全文评论。
- `wiki` 链接会先解析到真实对象，再决定能否评论。
- 会议来源支持飞书会议纪要、逐字稿、Minutes，以及人工整理的会议纪要。
- 默认流程先产出 comment plan，再执行写入，避免误写。

## 快速开始

```powershell
pip install -r requirements.txt
```

确保已经满足以下前置条件：

- 本机已安装 `lark-cli`
- 已完成 `lark-cli config init`
- 已按需要完成 `lark-cli auth login`
- 应用已经具备读取会议/文档、创建评论所需 scope

如果你要让 Codex 直接使用这个 skill，可以用类似下面的提示：

```text
Use $lark-meeting-doc-sync at C:\Users\hp\Desktop\Lark-PRD-Bridge\skills\lark-meeting-doc-sync to analyze the completed meeting at <meeting source> and sync comments into <target doc url>. Preview the comment plan before writing comments.
```

## 主流程命令

推荐直接使用仓库根目录下的 PowerShell 包装器：

```powershell
powershell -ExecutionPolicy Bypass -File .\run-meeting-doc-sync.ps1 `
  -TargetDoc "https://xxx.feishu.cn/docx/target_doc_token" `
  -MinuteUrl "https://xxx.feishu.cn/minutes/obxxxxxxxxxxxxxxxx"
```

确认 comment plan 后，直接加 `-Apply`：

```powershell
powershell -ExecutionPolicy Bypass -File .\run-meeting-doc-sync.ps1 `
  -TargetDoc "https://xxx.feishu.cn/docx/target_doc_token" `
  -MinuteUrl "https://xxx.feishu.cn/minutes/obxxxxxxxxxxxxxxxx" `
  -Apply `
  -MinConfidence high `
  -ApplyLimit 5 `
  -ApplyDelaySeconds 8
```

包装器会自动：

- 从 `minutes` 链接里提取 `minute_token`
- 默认绕过坏掉的本地代理环境
- 调用主流程脚本生成 comment plan
- 在 `-Apply` 时低频串行写评论，降低 429 风险

离线样例预览：

```powershell
python .\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py `
  --target-doc-json .\examples\sample_target_doc.json `
  --meeting-file .\examples\sample_meeting_notes.md `
  --output-dir .\artifacts\sample-run
```

用飞书会议纪要文档做预览：

```powershell
python .\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py `
  --target-doc "https://xxx.feishu.cn/docx/target_doc_token" `
  --meeting-doc "https://xxx.feishu.cn/docx/meeting_note_token" `
  --output-dir .\artifacts\prd-review-run
```

用 `minute_token` 做预览：

```powershell
python .\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py `
  --target-doc "https://xxx.feishu.cn/docx/target_doc_token" `
  --minute-tokens obxxxxxxxxxxxxxxxx `
  --meeting-artifact auto `
  --output-dir .\artifacts\minute-run
```

确认无误后实际写回评论：

```powershell
python .\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py `
  --target-doc "https://xxx.feishu.cn/docx/target_doc_token" `
  --meeting-doc "https://xxx.feishu.cn/docx/meeting_note_token" `
  --output-dir .\artifacts\apply-run `
  --apply `
  --allow-full-comments `
  --min-confidence high
```

默认行为：

- 默认只生成计划，不写回。
- `--apply` 才会真正调用 `lark-cli drive +add-comment`。
- 脚本默认会绕过坏掉的本地代理环境；如果你明确要保留代理，用 `--keep-proxy`。

## 辅助脚本

如果你只想单独运行仓库里的辅助脚本：

```powershell
python .\skills\lark-meeting-doc-sync\scripts\extract_doc_structure.py --input .\examples\sample_target_doc.json --output .\artifacts\doc-structure.json
python .\skills\lark-meeting-doc-sync\scripts\build_comment_plan.py --doc-structure .\artifacts\doc-structure.json --meeting .\examples\sample_meeting_notes.md --output .\artifacts\comment-plan.json
```

## 产物说明

每次运行都会在 `output-dir` 里落这些文件：

- `target-doc.json`
- `meeting-notes.md`
- `doc-structure.json`
- `comment-plan.json`
- `run-summary.json`
- `apply-results.json`，仅在 `--apply` 时生成

## 推荐工作流

1. 用 `lark-vc` 或 `lark-minutes` 拿到会议纪要、总结或逐字稿。
2. 用 `lark-doc` 获取目标文档内容。
3. 用 `sync_lark_comments.py` 生成结构化 section map 和 comment plan 草稿。
4. 让 Codex 基于 skill 审核这些草稿，决定每条评论是全文评论还是局部评论。
5. 在确认后用同一个主流程脚本直接写回文档。

## 仓库结构

- `skills/lark-meeting-doc-sync/`
  包含真正可复用的 skill 说明、参考规则和辅助脚本。
- `examples/`
  包含一个目标文档样例和一个会议纪要样例，便于本地验证脚本。
- `requirements.txt`
  当前脚本只依赖 Python 标准库，保留这个文件是为了统一项目入口。

## 扩展方向

- 支持更强的 section 定位策略，例如直接落到 block id。
- 增加 comment plan 的审批环节，例如“只写高置信度评论”。
- 支持同一场会议同步到多个文档。
- 增加不同文档类型的 target adapter，而不是只围绕 PRD。

git init
git add .
git commit -m "feat: bootstrap lark meeting doc sync skill"
git branch -M main
git remote add origin https://github.com/<your-account>/lark-prd-bridge.git
git push -u origin main
```
