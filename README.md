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

## 4. Xserver VPSへのデプロイ手順 (Deployment to Xserver VPS)

このセクションでは、本アプリケーションをXserver VPSにデプロイし、Cloudflareを利用して常時SSL化（HTTPS）されたWebアプリとして公開する手順を解説します。

### 4.1. 前提条件

- **Xserver VPS契約**: サーバーが利用可能な状態であること。
- **ドメイン取得**: 公開に使用するドメインを取得済みであること。
- **ローカル環境**: `git`がインストールされていること。

### 4.2. サーバーの初期設定

Xserver VPSにSSHでログインし、基本的なツールをインストールします。

```bash
# apt-getの場合 (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git

# yumの場合 (CentOS)
sudo yum update -y
sudo yum install -y docker docker-compose git
sudo systemctl start docker
sudo systemctl enable docker
```

### 4.3. Cloudflareの設定

1.  **Cloudflareにサインアップ**し、取得したドメインをサイトとして追加します。
2.  DNS設定画面で、VPSのIPアドレスを指す**Aレコード**を作成します。
    -   **タイプ**: A
    -   **名前**: `example.com` (ドメイン名) または `@`
    -   **IPv4アドレス**: Xserver VPSのIPアドレス
    -   **プロキシステータス**: **プロキシ済み**（オレンジ色の雲アイコン）に設定します。
3.  `www`などのサブドメインも使用する場合は、同様にAレコードまたはCNAMEレコードを追加します。

### 4.4. SSL証明書の準備 (Cloudflare Origin CA)

Cloudflareの「フル (厳密)」SSLモードを利用するため、サーバーとCloudflare間の通信を暗号化する**Origin CA証明書**を無料で発行します。

1.  Cloudflareダッシュボードで、**[SSL/TLS] > [オリジンサーバー]** タブに移動します。
2.  **「証明書を作成する」** をクリックします。
3.  デフォルト設定のまま **「作成」** をクリックします。
4.  **オリジン証明書**と**プライベートキー**が生成されます。これらをコピーして、それぞれ `nginx.crt` と `nginx.key` という名前でローカルPCに保存します。

### 4.5. アプリケーションのデプロイ

1.  **リポジトリをクローンします。**
    ローカルPCで、ターミナルを開き、リポジトリをクローンします。
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **SSL証明書を配置します。**
    先ほど保存した `nginx.crt` と `nginx.key` を、プロジェクト内の `nginx/certs/` ディレクトリに配置します。既存の自己署名証明書は上書きまたは削除してください。

3.  **Nginx設定ファイルを編集します。**
    `nginx/nginx.conf` を開き、`server_name` を `localhost` から自分のドメイン名に変更します。
    ```nginx
    # Before
    server_name localhost;

    # After
    server_name example.com www.example.com;
    ```

4.  **環境変数ファイルを作成します。**
    プロジェクトのルートに `.env` ファイルを作成し、OpenAI APIキーを設定します。
    ```
    OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ```

5.  **サーバーにプロジェクトをアップロードします。**
    `scp` や `rsync` などのツールを使い、プロジェクト全体をXserver VPSにアップロードします。
    ```bash
    # 例: rsyncを使用する場合 (ローカルPCから実行)
    rsync -avz --exclude '.git' --exclude '.idea' ./ user@your_vps_ip:/path/to/hanaview/
    ```

6.  **アプリケーションを起動します。**
    VPSにSSHでログインし、アップロードしたプロジェクトディレクトリに移動して、Docker Composeを起動します。
    ```bash
    cd /path/to/hanaview/
    sudo docker-compose up -d --build
    ```

### 4.6. Cloudflareの最終設定

1.  Cloudflareダッシュボードで、**[SSL/TLS] > [概要]** タブに移動します。
2.  SSL/TLS暗号化モードを **「フル (厳密)」 (Full (Strict))** に設定します。
3.  **[常にHTTPSを使用]** をオンにすることをお勧めします。

これで、`https://example.com` にアクセスすると、アプリケーションが表示されます。PWAとして「ホーム画面に追加」も可能なはずです。
