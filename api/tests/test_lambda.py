import json
import os

os.environ.setdefault("PANBIOME_BUCKET", "test-bucket")

from panbiome_api.lambda_handler import handler  # noqa: E402


def http_api_event(path):
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.execute-api.ap-south-1.amazonaws.com", "authorization": "Bearer t"},
        "requestContext": {
            "http": {"method": "GET", "path": path, "protocol": "HTTP/1.1", "sourceIp": "1.2.3.4", "userAgent": "t"},
            "authorizer": {"jwt": {"claims": {"email": "staff@example.org"}, "scopes": None}},
            "stage": "$default",
            "requestId": "r1",
        },
        "isBase64Encoded": False,
    }


def test_handler_serves_api_routes():
    res = handler(http_api_event("/api/pipeline"), None)
    assert res["statusCode"] == 200
    assert len(json.loads(res["body"])["processes"]) == 34
