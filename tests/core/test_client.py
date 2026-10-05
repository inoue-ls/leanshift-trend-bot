from core.analysis.client import build_http_options


def test_http_options_time_out_each_request_after_60_seconds() -> None:
    # 通信が切れて応答が返らないとき、いつまでも待たずに失敗させる
    assert build_http_options().timeout == 60_000


def test_http_options_keep_retrying_temporary_errors() -> None:
    options = build_http_options()
    assert options.retry_options is not None
    assert options.retry_options.attempts == 5
