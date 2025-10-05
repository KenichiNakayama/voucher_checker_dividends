# Technology Stack

## アーキテクチャ
現時点では単一のStreamlitアプリ（`app.py`）として構成され、UIからバウチャー検証ロジックを呼び出す構造を想定しています。

## 使用技術
### 言語とフレームワーク
- Python 3（仮想環境 `env/` が配置）
- Streamlit：UI構築

### 依存関係
- `requirements.txt` は未作成。必要なライブラリは今後明示的に追加する想定です。

## 開発環境
### 必要なツール
- Python 3.x
- pip
- Streamlit
- 仮想環境管理ツール（`venv` など）

### よく使うコマンド
- 起動：`streamlit run app.py`
- テスト：未整備（`pytest` 導入を想定）
- ビルド：該当なし
- 仮想環境の有効化：`source env/bin/activate`

## 環境変数
- 現時点で特になし
