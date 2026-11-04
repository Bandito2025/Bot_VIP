import urllib.request
import json
import logging
import time

logger = logging.getLogger(__name__)

class WPPClient:
    def __init__(self, base_url="http://127.0.0.1:8090", api_key="Lw8RaZZKE095ccmS07xSfGshnGiS3U3JiRnkqpOP5b0"):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, endpoint, method="GET", payload=None):
        url = f"{self.base_url}/wpp-api/v1{endpoint}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Ошибка обращения к WPP API ({endpoint}): {e}")
            return {"ok": False, "error": str(e)}

    def create_client_bundle(self, user_tg_id: int):
        """Создает для пользователя связку VLESS + Hysteria2 с паузой между вызовами"""
        configs = []
        profile_ids = []
        name = f"user_{user_tg_id}"

        for proto in ["vless", "hysteria"]:
            res = self._request("/profiles/create", method="POST", payload={"protocol": proto, "name": name})
            if res.get("ok") and "profile" in res:
                prof = res["profile"]
                configs.append(prof.get("link"))
                profile_ids.append(prof.get("id"))
            time.sleep(1) # Пауза для завершения перезагрузки конфигурации Xray

        return {
            "configs": [c for c in configs if c],
            "profile_ids": profile_ids
        }

    def delete_profile(self, profile_id: str):
        return self._request("/profiles/delete", method="POST", payload={"id": profile_id})

    def list_profiles(self):
        return self._request("/profiles", method="GET")
