# HanaView Market Dashboard

## 1. 概要 (Overview)

HanaViewは、個人投資家が毎朝の市場チェックを効率化するための統合ダッシュボードです。
このアプリケーションは、VIX、Fear & Greed Index、米国10年債などの主要な市場指標、S&P 500とNASDAQ 100のヒートマップ、経済指標カレンダーなどを一元的に表示します。

データは毎日定時に自動で更新されますが、管理者が手動で更新プロセスを実行することも可能です。

## 2. セットアップ手順 (Setup)

### 前提条件
- Docker
- Docker Compose
- `git`

### インストールと起動
1.  **リポジトリをクローンします。**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **環境変数ファイルを作成します。**
    プロジェクトのルートに `.env` ファイルを作成し、OpenAI APIキーを設定します。
    ```
    OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ```

3.  **Dockerコンテナをビルドして起動します。**
    ```bash
    docker-compose up -d --build
    ```
    初回起動には数分かかることがあります。

4.  **アプリケーションにアクセスします。**
    ブラウザで `http://localhost:8000` を開きます。

## 3. 手動でのデータ更新 (Manual Data Update)

データはcronによって自動的に更新されますが、管理者は以下の手順で手動で更新プロセスをトリガーできます。

1.  **実行中のコンテナ内でbashセッションを開始します。**
    ```bash
    docker-compose exec app bash
    ```

2.  **データ取得 (fetch) を実行します。**
    コンテナ内で以下のコマンドを実行すると、外部APIから最新の生データが取得され、`data/data_raw.json` に保存されます。
    **注意:** この処理は、S&P 500とNASDAQ 100の全銘柄（約600）の情報を取得するため、完了までに5〜10分程度かかる場合があります。
    ```bash
    python backend/data_fetcher.py fetch
    ```

3.  **レポート生成 (generate) を実行します。**
    `fetch`が完了したら、以下のコマンドを実行します。これにより、`data_raw.json` が読み込まれ、AIによる解説（設定済みの場合）が追加され、最終的なデータファイル `data/data_YYYY-MM-DD.json` および `data/data.json` が生成されます。
    ```bash
    python backend/data_fetcher.py generate
    ```

これで、フロントエンドに表示されるデータが手動で更新されます。
