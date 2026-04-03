# Workflow Recipes

LLM に MCP ツールの自動使用を指令するワークフローレシピ。
`behavior_compiler.py` がビルド時に読み込み、MCP initialize response の instructions フィールドに注入する。

## ワークフロー追加手順

1. 既存の YAML をコピーしてテンプレートにする
2. 全フィールドを記入（スキーマは下記参照）
3. `task docker:restart` でビルド → バリデーションエラーがないか確認（ログに出る）
4. Claude Code で実際にタスクを投げて、ワークフローが発火するか確認
5. PR を作成

## YAML スキーマ

```yaml
name: kebab-case-name          # 一意な識別子
description: "人間向けの説明"    # ドキュメント用（LLM には送信しない）
priority: high                  # high | medium | low
max_tokens: 200                 # compile_to のトークン上限（超過でビルドエラー）
servers:                        # カバーするサーバー名リスト
  - server-name
trigger: "トリガー条件の説明"    # ドキュメント用（ランタイムマッチングなし）
compile_to: |                   # instructions に注入する確定テキスト
  ### Section Title
  WHEN condition:
  1. FIRST: Call tool:name
  2. THEN: Next step
  NEVER skip this.
```

## 指令文の書き方

- **MUST, FIRST, THEN, NEVER** を使う（提案ではなく指令）
- 理由を添える（例: `Your training data is outdated.`）
- 1ワークフロー ~150-200 tokens 以内
- `compile_to` は英語で書く（LLM のシステムプロンプトに注入されるため）
- トークンバジェット: ワークフロー全体で ~800 tokens。3-5個が上限

## Priority

- `high`: 必ず instructions に含まれる
- `medium`: high のバジェット消費後、余裕があれば含まれる
- `low`: 大幅に余裕がある場合のみ
