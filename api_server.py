import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from nationwide_platform.barcode_ingest import (
    describe_ingest_integrations,
    ingest_barcode_scan_payload,
)
from nationwide_platform.api_service import (
    compare_basket,
    get_collection_program_status,
    get_city_markets,
    get_contract_price_history,
    get_contract_pricing_alternatives,
    get_contract_product_offers,
    get_platform_status,
    list_cities,
    lookup_barcode,
    search_contract_products,
    search_offers,
)


HOST = "127.0.0.1"
PORT = 8040


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "MarketGelsinAPI/0.2"

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True}, status=HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        try:
            if path == "/health":
                self._send_json({"ok": True, "service": "market-gelsin-api"})
                return

            if path.startswith("/v1/products/") and path.endswith("/offers"):
                barcode = path.split("/")[3]
                city_code = _optional_single(query, "city_code")
                district = _optional_single(query, "district")
                limit = int(_optional_single(query, "limit") or 50)
                include_out_of_stock = _optional_bool(query, "include_out_of_stock", default=False)
                self._send_json(
                    get_contract_product_offers(
                        barcode=barcode,
                        city_code=city_code,
                        district=district,
                        limit=limit,
                        include_out_of_stock=include_out_of_stock,
                    )
                )
                return

            if path.startswith("/v1/products/") and path.endswith("/price-history"):
                barcode = path.split("/")[3]
                city_code = _optional_single(query, "city_code")
                market_name = _optional_single(query, "market_name")
                days = int(_optional_single(query, "days") or 30)
                self._send_json(
                    get_contract_price_history(
                        barcode=barcode,
                        city_code=city_code,
                        market_name=market_name,
                        days=days,
                    )
                )
                return

            if path == "/v1/search/products":
                search_query = _required_single(query, "q")
                city_code = _optional_single(query, "city_code")
                category = _optional_single(query, "category")
                brand = _optional_single(query, "brand")
                limit = int(_optional_single(query, "limit") or 20)
                self._send_json(
                    search_contract_products(
                        q=search_query,
                        city_code=city_code,
                        category=category,
                        brand=brand,
                        limit=limit,
                    )
                )
                return

            if path == "/api/v1/status":
                self._send_json(get_platform_status())
                return

            if path == "/api/v1/program/coverage":
                self._send_json(get_collection_program_status())
                return

            if path in {"/api/v1/integrations/status", "/api/v1/barcode/scans/status"}:
                self._send_json(describe_ingest_integrations())
                return

            if path == "/api/v1/cities":
                self._send_json({"cities": list_cities()})
                return

            if path.startswith("/api/v1/cities/") and path.endswith("/markets"):
                city_slug = path.split("/")[4]
                self._send_json({"city_slug": city_slug, "markets": get_city_markets(city_slug)})
                return

            if path == "/api/v1/offers":
                city_slug = _required_single(query, "city")
                market_key = _optional_single(query, "market_key")
                search_query = _optional_single(query, "q")
                barcode = _optional_single(query, "barcode")
                limit = int(_optional_single(query, "limit") or 50)
                self._send_json(
                    {
                        "city_slug": city_slug,
                        "offers": search_offers(
                            city_slug=city_slug,
                            query=search_query,
                            market_key=market_key,
                            barcode=barcode,
                            limit=limit,
                        ),
                    }
                )
                return

            if path.startswith("/api/v1/barcode/"):
                barcode = path.split("/")[4]
                self._send_json(lookup_barcode(barcode))
                return

            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            error_code = "bad_request"
            if str(exc) in {"invalid_barcode", "invalid_city_code", "invalid_days", "invalid_scan_count", "batch_limit_exceeded"}:
                error_code = str(exc)
            self._send_json({"error": error_code, "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self._send_json({"error": "unauthorized", "detail": str(exc)}, status=HTTPStatus.UNAUTHORIZED)
        except Exception as exc:
            self._send_json({"error": "internal_error", "detail": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path in {"/api/v1/barcode/scans", "/api/v1/barcode/scans/batch"}:
                _ensure_ingest_authorized(self.headers)
                payload = _read_json_body(self)
                self._send_json(ingest_barcode_scan_payload(payload))
                return

            if path == "/v1/pricing/alternatives":
                payload = _read_json_body(self)
                city_code = payload.get("city_code")
                barcode = payload.get("barcode")
                candidate_barcodes = payload.get("candidate_barcodes") or []
                if not city_code:
                    raise ValueError("city_code is required")
                if not barcode:
                    raise ValueError("barcode is required")
                if not isinstance(candidate_barcodes, list):
                    raise ValueError("candidate_barcodes must be a list")
                self._send_json(
                    get_contract_pricing_alternatives(
                        city_code=str(city_code),
                        barcode=str(barcode),
                        candidate_barcodes=[str(item) for item in candidate_barcodes],
                    )
                )
                return

            if path != "/api/v1/basket/compare":
                self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                return

            payload = _read_json_body(self)
            city_slug = payload.get("city_slug")
            items = payload.get("items") or []
            min_score = float(payload.get("min_score") or 0.35)
            if not city_slug:
                raise ValueError("city_slug is required")
            if not isinstance(items, list):
                raise ValueError("items must be a list")
            self._send_json(compare_basket(city_slug=city_slug, items=items, min_score=min_score))
        except ValueError as exc:
            error_code = "bad_request"
            if str(exc) in {"invalid_barcode", "invalid_city_code", "invalid_days", "invalid_scan_count", "batch_limit_exceeded"}:
                error_code = str(exc)
            self._send_json({"error": error_code, "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self._send_json({"error": "unauthorized", "detail": str(exc)}, status=HTTPStatus.UNAUTHORIZED)
        except Exception as exc:
            self._send_json({"error": "internal_error", "detail": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = b""
        if status != HTTPStatus.NO_CONTENT:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


def _required_single(query: dict, key: str) -> str:
    value = _optional_single(query, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_single(query: dict, key: str):
    values = query.get(key) or []
    return values[0] if values else None


def _optional_bool(query: dict, key: str, default: bool = False) -> bool:
    value = _optional_single(query, key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _read_json_body(handler: BaseHTTPRequestHandler):
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw_body = handler.rfile.read(content_length) if content_length else b"{}"
    try:
        return json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc


def _ensure_ingest_authorized(headers) -> None:
    expected_token = os.getenv("MARKET_GELSIN_INGEST_TOKEN", "").strip()
    if not expected_token:
        return

    authorization = headers.get("Authorization", "")
    provided_token = None
    if authorization.lower().startswith("bearer "):
        provided_token = authorization.split(" ", 1)[1].strip()
    if not provided_token:
        provided_token = headers.get("X-API-Key", "").strip()
    if provided_token != expected_token:
        raise PermissionError("invalid ingest token")


def main() -> int:
    with ThreadingHTTPServer((HOST, PORT), ApiHandler) as server:
        print(f"Market API listening on http://{HOST}:{PORT}")
        server.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
