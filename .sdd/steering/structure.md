# Project Structure

## ルートディレクトリ構成
```
/
├── app.py          # Streamlitアプリのエントリーポイント（現状内容なし）
├── README.md       # プロジェクト概要
├── AGENTS.md       # リポジトリガイドライン
├── .sdd/           # SDDドキュメント
│   ├── README.md
│   ├── description.md
│   ├── specs/
│   └── steering/
└── env/            # ローカル仮想環境
```

## コード構成パターン
Streamlit UIを `app.py` にまとめ、バウチャー検証ロジックは再利用可能なヘルパーモジュール（例：`voucher_logic/validators.py`）として分離する想定です。

## ファイル命名規則
- Pythonの関数・変数・ウィジェットキー：snake_case
- クラス名：PascalCase

## 主要な設計原則
- StreamlitのUIはトップダウンで宣言し、副作用は専用関数に隔離します。
- バウチャー検証ロジックはテストしやすいようモジュール化します。
- 依存関係は仮想環境で管理し、`requirements.txt` で明示します。
