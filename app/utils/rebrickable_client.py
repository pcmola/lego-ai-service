import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class RebrickablePart:
    part_num: str
    name: str
    image_url: str


class RebrickableClient:
    BASE_URL = "https://rebrickable.com/api/v3/lego"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 5.0):
        self.api_key = api_key or os.getenv("REBRICKABLE_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            logger.warning(
                "[RebrickableClient] REBRICKABLE_API_KEY 가 설정되지 않았습니다. "
                "브릭/부품 정보 조회는 '-' 로 대체됩니다."
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"key {self.api_key}",
            "Accept": "application/json",
        }

    def _log_request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None):
        logger.info(
            "[Rebrickable API Request] method=%s url=%s params=%s",
            method,
            url,
            params,
        )

    def _log_response(self, status_code: int, data: Optional[Dict[str, Any]]):
        preview = None
        if isinstance(data, dict):
            preview = str(data)
            if len(preview) > 500:
                preview = preview[:500] + "...(truncated)"
        logger.info(
            "[Rebrickable API Response] status=%s body_preview=%s",
            status_code,
            preview,
        )

    def get_part(self, part_num: str) -> Optional[RebrickablePart]:
        if not self.api_key:
            logger.warning(
                "[RebrickableClient] API Key 미설정 상태에서 get_part(%s) 호출되었습니다.",
                part_num,
            )
            return None

        if requests is None:
            logger.error(
                "[RebrickableClient] 'requests' 라이브러리가 설치되어 있지 않습니다. "
                "pip install requests 후 다시 시도하세요."
            )
            return None

        url = f"{self.BASE_URL}/parts/{part_num}/"
        params: Dict[str, Any] = {}

        try:
            self._log_request("GET", url, params)
            resp = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            status = resp.status_code

            try:
                data: Optional[Dict[str, Any]] = resp.json()
            except Exception:
                data = None

            self._log_response(status, data)

            if not (200 <= status < 300) or not isinstance(data, dict):
                logger.error(
                    "[RebrickableClient] get_part(%s) 실패: status=%s, body=%s",
                    part_num,
                    status,
                    data,
                )
                return None

            part_num_val = str(data.get("part_num") or part_num)
            name_val = str(data.get("name") or "-")
            img_val = str(data.get("part_img_url") or "")

            if not img_val:
                logger.warning(
                    "[RebrickableClient] get_part(%s) 성공했지만 이미지 URL 이 없습니다.",
                    part_num,
                )

            return RebrickablePart(
                part_num=part_num_val,
                name=name_val,
                image_url=img_val,
            )

        except Exception as e:
            logger.exception(
                "[RebrickableClient] get_part(%s) 호출 중 예외 발생: %s",
                part_num,
                e,
            )
            return None
