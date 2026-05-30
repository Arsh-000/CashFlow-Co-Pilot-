from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

REST_URL = f"{settings.SUPABASE_URL}/rest/v1"
AUTH_URL = f"{settings.SUPABASE_URL}/auth/v1"

_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY.strip()

http_client = httpx.Client(timeout=30.0, http2=False)


def rest_write_headers() -> dict[str, str]:
    return {
        "apikey": _SERVICE_KEY,
        "Authorization": f"Bearer {_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def rest_read_headers(*, single: bool = False) -> dict[str, str]:
    headers = {
        "apikey": _SERVICE_KEY,
        "Authorization": f"Bearer {_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if single:
        headers["Accept"] = "application/vnd.pgrst.object+json"
    return headers


def auth_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass
class QueryResponse:
    data: Any


class TableQuery:
    def __init__(self, table_name: str) -> None:
        self._table = table_name
        self._select = "*"
        self._filters: list[tuple[str, str]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._single = False
        self._insert_data: dict | list | None = None

    def select(self, columns: str) -> "TableQuery":
        self._select = columns
        return self

    def eq(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, f"eq.{value}"))
        return self

    def order(self, column: str, desc: bool = False) -> "TableQuery":
        self._order = (column, desc)
        return self

    def limit(self, count: int) -> "TableQuery":
        self._limit = count
        return self

    def single(self) -> "TableQuery":
        self._single = True
        return self

    def insert(self, data: dict | list) -> "TableQuery":
        self._insert_data = data
        return self

    def execute(self) -> QueryResponse:
        if self._insert_data is not None:
            return self._execute_insert()
        return self._execute_select()

    def _execute_insert(self) -> QueryResponse:
        payload = (
            self._insert_data
            if isinstance(self._insert_data, list)
            else [self._insert_data]
        )
        response = http_client.post(
            f"{REST_URL}/{self._table}",
            headers=rest_write_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data = [data]
        return QueryResponse(data=data)

    def _execute_select(self) -> QueryResponse:
        params: dict[str, str] = {"select": self._select}
        for column, filter_value in self._filters:
            params[column] = filter_value
        if self._order:
            column, desc = self._order
            params["order"] = f"{column}.desc" if desc else column
        if self._limit is not None:
            params["limit"] = str(self._limit)

        response = http_client.get(
            f"{REST_URL}/{self._table}",
            headers=rest_read_headers(single=self._single),
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        if self._single:
            return QueryResponse(data=data)
        return QueryResponse(data=data if isinstance(data, list) else [data])


class SupabaseRestClient:
    def table(self, name: str) -> TableQuery:
        return TableQuery(name)


supabase = SupabaseRestClient()
