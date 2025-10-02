import os
import requests
import json
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# Cloudflareの認証情報を環境変数から取得
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_NAMESPACE_ID = os.getenv('CF_NAMESPACE_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')

# --- ここからテスト ---

def test_kv_connection():
    """Cloudflare KVとの接続をテストする関数"""

    # 必須情報が設定されているかチェック
    if not all([CF_ACCOUNT_ID, CF_NAMESPACE_ID, CF_API_TOKEN]):
        print("エラー: .envファイルに必要な情報（CF_ACCOUNT_ID, CF_NAMESPACE_ID, CF_API_TOKEN）が設定されていません。")
        return

    # APIのエンドポイントURLを構築
    # {key} の部分は後で書き換える
    base_url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_NAMESPACE_ID}/values"

    # 認証用のヘッダー
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }

    # テスト用のキーとデータ
    test_key = "test_user_12345"
    test_data = {
        "message": "Hello, Cloudflare KV!",
        "timestamp": "2025-10-02T12:00:00Z"
    }

    print("--- Cloudflare KV 接続テスト開始 ---")

    # 1. データの書き込み (PUTリクエスト)
    try:
        print(f"\n[1/3] '{test_key}' にデータを書き込んでいます...")
        write_url = f"{base_url}/{test_key}"
        # Cloudflare KVはデータを文字列として保存するため、JSONを文字列に変換する
        response = requests.put(write_url, headers=headers, data=json.dumps(test_data))
        response.raise_for_status()  # エラーがあれば例外を発生させる
        print(f"  -> 成功！ ステータスコード: {response.status_code}")
        # print(f"  -> レスポンス内容: {response.json()}")

    except requests.exceptions.RequestException as e:
        print(f"  -> 書き込みエラー: {e}")
        if e.response is not None:
            print(f"  -> エラー詳細: {e.response.text}")
        print("--- テスト中断 ---")
        return

    # 2. データの読み出し (GETリクエスト)
    try:
        print(f"\n[2/3] '{test_key}' のデータを読み出しています...")
        read_url = f"{base_url}/{test_key}"
        response = requests.get(read_url, headers=headers)
        response.raise_for_status()
        read_data = response.json()
        print(f"  -> 成功！ ステータスコード: {response.status_code}")
        print(f"  -> 読み出したデータ: {read_data}")

        # 検証
        if read_data == test_data:
            print("  -> 検証OK: 書き込んだデータと一致しました。")
        else:
            print("  -> 検証NG: 書き込んだデータと一致しません。")


    except requests.exceptions.RequestException as e:
        print(f"  -> 読み出しエラー: {e}")
        if e.response is not None:
            print(f"  -> エラー詳細: {e.response.text}")
        print("--- テスト中断 ---")
        return

    # 3. データの削除 (DELETEリクエスト)
    try:
        print(f"\n[3/3] '{test_key}' のデータを削除しています...")
        delete_url = f"{base_url}/{test_key}"
        response = requests.delete(delete_url, headers=headers)
        response.raise_for_status()
        print(f"  -> 成功！ ステータスコード: {response.status_code}")
        # print(f"  -> レスポンス内容: {response.json()}")

    except requests.exceptions.RequestException as e:
        print(f"  -> 削除エラー: {e}")
        if e.response is not None:
            print(f"  -> エラー詳細: {e.response.text}")
        print("--- テスト中断 ---")
        return

    print("\n--- 全てのテストが正常に完了しました！ ---")


if __name__ == "__main__":
    test_kv_connection()