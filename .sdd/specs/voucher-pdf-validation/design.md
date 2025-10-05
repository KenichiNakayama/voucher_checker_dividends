# 技術設計書

## アーキテクチャ概要
単一ページのStreamlitアプリ (`app.py`) から、PDF解析とAIベースの抽出ロジックを分離した `voucher_logic/` パッケージを呼び出す構成とする。UI層はユーザー操作と結果表示を担当し、ビジネスロジック層ではPDFテキスト抽出、要件検証、ハイライト生成、AI API呼び出しを分担する。解析エンジンはOpenAIまたはClaudeのどちらかを切り替えて利用できるよう抽象化されたクライアントを介して統合する。

## 主要コンポーネント
### コンポーネント1：Streamlit UI (`app.py`)
- 責務：ファイルアップロード、APIプロバイダ選択、解析実行トリガー、検証結果・抽出値・ハイライトPDFの表示とダウンロード提供。
- 入力：ユーザーがアップロードしたPDFファイル、APIプロバイダ選択、再解析トリガー。
- 出力：画面上の検証結果、抽出値テーブル、ハイライトプレビュー、ダウンロードボタン。
- 依存関係：`voucher_logic.controller.analyze_voucher`、`voucher_logic.models` のデータ構造、`streamlit`。

### コンポーネント2：Voucher解析コントローラ (`voucher_logic/controller.py`)
- 責務：PDF読み込み・AI抽出・検証・ハイライト生成の各サービスをオーケストレーションし、UIに返却する統合結果を組み立てる。
- 入力：`UploadedFile` 相当のファイルオブジェクト、選択された `ProviderType`、ユーザー指定オプション。
- 出力：`VoucherAnalysisResult`（検証ステータス、抽出フィールド、警告、ハイライト付きPDFバイナリ）。
- 依存関係：`PdfIngestor`、`VoucherExtractor`、`VoucherValidator`、`HighlightRenderer`、`LLMClientFactory`。

### コンポーネント3：PDFインジェスター (`voucher_logic/pdf_ingestor.py`)
- 責務：PDFをページ単位のテキストと座標情報に変換し、後続処理に渡す。
- 入力：PDFバイト列。
- 出力：`ParsedDocument`（ページテキスト、トークン座標、メタ情報）。
- 依存関係：`pdfplumber` などのPDF処理ライブラリ。

### コンポーネント4：バウチャー抽出サービス (`voucher_logic/extraction.py`)
- 責務：解析対象テキストを整形し、選択されたAIクライアントに渡して必要項目を抽出する。
- 入力：`ParsedDocument`、`ProviderType`。
- 出力：`ExtractedVoucherData`（会社名、決議日、金額、タイトル、信頼度、引用範囲情報）。
- 依存関係：`LLMClient` 実装、`prompt_templates`。

### コンポーネント5：検証サービス (`voucher_logic/validators.py`)
- 責務：抽出結果が要件（文書タイトル、会社名、決議日、金額）を満たしているか確認し、欠落・不明データを報告する。
- 入力：`ExtractedVoucherData`、業務ルール設定。
- 出力：`ValidationReport`（要件別フラグ、警告メッセージ）。
- 依存関係：`voucher_logic.models`。

### コンポーネント6：ハイライトレンダラー (`voucher_logic/highlight.py`)
- 責務：抽出結果に紐づく座標を用いてPDFにハイライト注釈を付与し、プレビュー用/ダウンロード用のPDFを生成する。
- 入力：原本PDFバイト列、`ExtractedVoucherData` 内の引用範囲。
- 出力：ハイライト済みPDFバイト列、プレビュー用画像（必要に応じ）。
- 依存関係：`reportlab` や `PyPDF2` などのPDF編集ライブラリ。

### コンポーネント7：AIクライアント (`voucher_logic/llm/clients.py`)
- 責務：OpenAI / Claude APIへのリクエストを統一インターフェースで提供し、レスポンスを正規化して返す。
- 入力：`LLMRequest`（プロンプト、システム指示、設定値）。
- 出力：`LLMResponse`（抽出結果JSON、引用情報、エラー情報）。
- 依存関係：`openai` SDK、`anthropic` SDK、環境変数（`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`）。

## データモデル
### `ParsedDocument`
- `pages`: `List[PageText]` — ページ番号と全文テキスト。
- `tokens`: `List[TextSpan]` — 各トークンの文字範囲と座標。
- `metadata`: `dict` — PDFのタイトルなど任意情報。

### `ExtractedVoucherData`
- `title`: `FieldValue` — 型: `Optional[str]`。配当決議文書タイトル。引用範囲ID付き。
- `company_name`: `FieldValue` — 型: `Optional[str]`。決議会社名。
- `resolution_date`: `FieldValue` — 型: `Optional[date]`。決議日。日付に変換できない場合はNoneとし理由付き。
- `dividend_amount`: `FieldValue` — 型: `Optional[Decimal]`。金額。通貨処理は後続対応。
- `others`: `Dict[str, FieldValue]` — 追加項目（例：議事録番号）。
- `source_highlights`: `List[HighlightSpan]` — 各フィールドに紐づくページ・座標。

### `ValidationReport`
- `requirements`: `Dict[str, RequirementStatus]` — 各要件の `status`（pass/fail/unknown）と `message`。
- `overall_status`: `Literal["pass","warning","fail"]`。

### `VoucherAnalysisResult`
- `extracted`: `ExtractedVoucherData`
- `validation`: `ValidationReport`
- `highlight_pdf`: `bytes` — ダウンロード用PDF。
- `errors`: `List[str]` — 致命的エラー説明。

### `ProviderType`
- Enum：`OPENAI`, `CLAUDE`

## 処理フロー
1. ユーザーがStreamlit UIでPDFをアップロードし、使用するAIプロバイダ（OpenAI/Claude）を選択する。
2. `app.py` がアップロードファイルを`voucher_logic.controller.analyze_voucher`に渡し、選択されたプロバイダも引数で指定する。
3. コントローラが`PdfIngestor`を呼び出してテキストと座標情報を取得する。失敗した場合はエラーを返す。
4. `LLMClientFactory` がプロバイダ種別に応じたクライアントを生成し、`VoucherExtractor` がプロンプトを構築してAI APIへリクエストする。
5. `VoucherExtractor` がAIレスポンスを`ExtractedVoucherData`にパースし、座標参照も取り込む。パースに失敗した場合はリカバリメッセージを返す。
6. `VoucherValidator` が抽出データを要件と照合し、`ValidationReport`を作成する。
7. `HighlightRenderer` が引用範囲に基づきPDFへハイライト注釈を付与し、ダウンロード用PDFバイト列を生成する。プレビュー用にページ画像を生成する場合はここで返す。
8. コントローラが抽出データ・検証結果・ハイライトPDFをまとめて`VoucherAnalysisResult`として返却し、UI層で表示・ダウンロード機能を提供する。

## エラーハンドリング
- エラーケース1：PDF読み込み失敗（破損・非PDF） → ユーザーに「ファイルを解析できません」と警告し、ログに詳細を残す。
- エラーケース2：APIキー未設定またはAPI呼び出し失敗 → 選択したプロバイダに対する設定不足メッセージをUIへ返し、別プロバイダへの切替を促す。
- エラーケース3：AIレスポンス解析失敗（期待形式でないJSON） → デフォルトのバリデーション結果をfail扱いで返し、再実行を促す。
- エラーケース4：ハイライト生成失敗 → 検証結果と抽出値は表示しつつ、ハイライトPDFのダウンロードは無効化し警告を表示する。

## 既存コードとの統合
- 変更が必要なファイル：
  - `app.py`：ファイルアップロードUI、プロバイダ選択、結果表示、ダウンロードボタンを実装し、`voucher_logic` パッケージを呼び出す。
- 新規作成ファイル：
  - `voucher_logic/__init__.py`：パッケージ初期化。
  - `voucher_logic/controller.py`：オーケストレーション関数。
  - `voucher_logic/models.py`：データクラスとEnum定義。
  - `voucher_logic/pdf_ingestor.py`：PDF解析ユーティリティ。
  - `voucher_logic/extraction.py`：抽出ロジックとプロンプト管理。
  - `voucher_logic/validators.py`：要件検証。
  - `voucher_logic/highlight.py`：ハイライトPDF生成。
  - `voucher_logic/llm/__init__.py`：LLMサブパッケージ初期化。
  - `voucher_logic/llm/clients.py`：OpenAI/Claudeクライアント実装とファクトリー。
  - `voucher_logic/prompt_templates.py`：AIプロンプトテンプレート定義（必要に応じて）。
  - `tests/` 配下各モジュール用テストファイル：例 `tests/test_controller.py`、`tests/test_validators.py`。
