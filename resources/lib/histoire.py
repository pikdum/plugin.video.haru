#!/usr/bin/env python3
import requests

HISTOIRE_URL = "https://histoire.pikdum.dev"


class Histoire:
    def __init__(self, base_url=HISTOIRE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def shows(self, query=None):
        params = {"q": query} if query else None
        return self._get("/api/v1/shows", params=params)

    def shows_by_id(self, ids, chunk_size=500):
        """Summaries for just these shows, in chunks that keep the URL short."""
        ids = sorted({int(show_id) for show_id in ids})
        shows = []
        for start in range(0, len(ids), chunk_size):
            chunk = ",".join(map(str, ids[start : start + chunk_size]))
            shows.extend(self._get("/api/v1/shows", params={"ids": chunk}))
        return shows

    def show(self, show_id):
        return self._get(f"/api/v1/shows/{show_id}")

    def schedule(self):
        return self._get("/api/v1/schedule")

    def download_files(self, download_id):
        return self._get(f"/api/v1/downloads/{download_id}/files")

    def _get(self, path, params=None):
        response = self.session.get(
            f"{self.base_url}{path}", params=params, timeout=(5, 30)
        )
        response.raise_for_status()
        return response.json()["data"]
