import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "models/gemini-2.5-flash-lite"


def build_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    # google-genai はデフォルトでリトライ無効(1回失敗即エラー)のため、
    # 503(高負荷)等の一時的なエラーに備えて明示的に有効化する。
    retry_options = types.HttpRetryOptions(
        attempts=5,
        initial_delay=2.0,
        max_delay=30.0,
        exp_base=2.0,
        jitter=1.0,
    )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(retry_options=retry_options),
    )
