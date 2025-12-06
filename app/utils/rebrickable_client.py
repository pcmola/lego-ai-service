import os
import logging
import time
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)


class RebrickableClient:
    """
    Rebrickable API 간단 클라이언트.

    - 기본 사용:
        client = RebrickableClient()
        part = client.resolve_part("3001", "Brick 2 x 4 red")
    """

    BASE_URL = "https://rebrickable.com/api/v3/lego"
    # 너무 과한 호출 방지를 위한 최소 간격(초) – 1초 권장
    MIN_INTERVAL = 1.0

    # 아주 단순한 메모리 캐시 (프로세스 살아있는 동안만 유지)
    _part_cache: Dict[str, Dict[str, Any]] = {}
    _last_call_ts: float = 0.0

    def __init__(self) -> None:
        self.api_key = os.getenv("REBRICKABLE_API_KEY", "").strip()
        if not self.api_key:
            logger.warning(
                "[RebrickableClient] REBRICKABLE_API_KEY 환경 변수가 설정되지 않았습니다."
            )

        self.session = requests.Session()

    # --------------------------------------------------------
    # 내부 유틸
    # --------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"key {self.api_key}",
        }

    def _throttle(self) -> None:
        """연속 호출 시 1초 간격을 맞추기 위한 간단한 rate limit."""
        now = time.time()
        elapsed = now - self._last_call_ts
        if elapsed < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - elapsed)
        self._last_call_ts = time.time()

    def _get(self, url: str, *, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """공통 GET 요청 래퍼."""
        if not self.api_key:
            logger.debug("[RebrickableClient] API 키 없음, 호출 스킵: %s", url)
            return None

        self._throttle()

        try:
            resp = self.session.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=10,
            )
        except Exception as e:
            logger.exception("[RebrickableClient] 요청 예외: %s (%s)", url, e)
            return None

        if resp.status_code != 200:
            logger.info(
                "[RebrickableClient] GET 실패: %s status=%s, body=%s",
                url,
                resp.status_code,
                resp.text[:200],
            )
            return None

        try:
            return resp.json()
        except Exception as e:
            logger.exception("[RebrickableClient] JSON 파싱 실패: %s (%s)", url, e)
            return None

    # --------------------------------------------------------
    # 공개 메서드
    # --------------------------------------------------------
    def get_part_by_num(self, part_num: str) -> Optional[Dict[str, Any]]:
        """
        정확한 part_num 으로 파트 조회.
        예) "3001", "3023", "32524"
        """
        if not part_num:
            return None

        part_num = part_num.strip()
        if not part_num or part_num in ("-", "0"):
            return None

        # 캐시 먼저 확인
        if part_num in self._part_cache:
            return self._part_cache[part_num]

        url = f"{self.BASE_URL}/parts/{part_num}/"
        data = self._get(url)
        if data:
            self._part_cache[part_num] = data
        return data

    def search_part_by_text(self, query: str) -> Optional[Dict[str, Any]]:
        """
        텍스트로 파트 검색 → 가장 우선순위 높은 결과 1개만 반환.
        예) "Brick 2 x 4", "Plate 1 x 2", "Technic Beam 1 x 7"
        """
        query = (query or "").strip()
        if not query or query in ("-",):
            return None

        # 캐시는 'SEARCH::쿼리' 형식의 키 사용
        cache_key = f"SEARCH::{query}"
        if cache_key in self._part_cache:
            return self._part_cache[cache_key]

        url = f"{self.BASE_URL}/parts/"
        params = {
            "search": query,
            "page_size": 1,  # 가장 잘 맞는 1개만
        }
        data = self._get(url, params=params)
        if not data:
            return None

        results = data.get("results") or []
        if not results:
            return None

        part = results[0]
        self._part_cache[cache_key] = part
        return part

    def resolve_part(
        self,
        part_num: Optional[str],
        hint_text: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        파트 번호와 힌트 텍스트를 함께 사용해 파트를 찾는다.

        1순위: part_num 으로 정확 조회
        2순위: hint_text (부품 이름/용도/사이즈 등) 으로 검색
        둘 다 실패하면 None 반환.
        """
        part_num = (part_num or "").strip()
        hint_text = (hint_text or "").strip()

        # 1) 번호 우선
        if part_num and part_num not in ("-", "0"):
            data = self.get_part_by_num(part_num)
            if data:
                logger.debug(
                    "[RebrickableClient] part_num 로 파트 식별 성공: %s (%s)",
                    part_num,
                    data.get("name"),
                )
                return data

        # 2) 번호가 없거나 실패 → 텍스트 검색
        if hint_text:
            data = self.search_part_by_text(hint_text)
            if data:
                logger.debug(
                    "[RebrickableClient] 텍스트 검색으로 파트 식별 성공: '%s' -> %s",
                    hint_text,
                    data.get("part_num"),
                )
                return data

        logger.debug(
            "[RebrickableClient] 파트 식별 실패: part_num='%s', hint_text='%s'",
            part_num,
            hint_text,
        )
        return None
