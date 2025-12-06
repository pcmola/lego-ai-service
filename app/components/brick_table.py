from __future__ import annotations

import html
import logging
from typing import List, Dict, Any, Optional

from utils.rebrickable_client import RebrickableClient, RebrickablePart

logger = logging.getLogger(__name__)


def _safe_get(d: Dict[str, Any], key: str, default: str = "-") -> str:
    val = d.get(key)
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def _lookup_part_with_rebrickable(
    row: Dict[str, Any],
    client: Optional[RebrickableClient],
) -> Dict[str, Any]:
    result = {
        "part_num": "-",
        "part_name": "-",
        "image_html": "-",
    }

    if client is None:
        logger.warning(
            "[brick_table] RebrickableClient 가 주어지지 않아 "
            "부품 정보가 '-' 로 대체됩니다."
        )
        return result

    raw_part_num = _safe_get(row, "part_num", "").replace(" ", "")
    if not raw_part_num:
        logger.warning(
            "[brick_table] row 에 part_num 이 없어 Rebrickable 조회를 건너뜁니다. row=%s",
            row,
        )
        return result

    logger.info(
        "[brick_table] Rebrickable get_part 호출 준비: part_num=%s, row=%s",
        raw_part_num,
        row,
    )
    part: Optional[RebrickablePart] = client.get_part(raw_part_num)

    if not part:
        logger.error(
            "[brick_table] Rebrickable get_part 실패: part_num=%s → '-', '-', '-' 로 대체",
            raw_part_num,
        )
        return result

    image_html = "-"
    if part.image_url:
        safe_url = html.escape(part.image_url, quote=True)
        safe_alt = html.escape(part.name or part.part_num)
        image_html = (
            f"<img src='{safe_url}' alt='{safe_alt}' "
            f"style='max-width:80px; max-height:80px;' />"
        )

    result["part_num"] = part.part_num or "-"
    result["part_name"] = part.name or "-"
    result["image_html"] = image_html

    logger.info(
        "[brick_table] Rebrickable get_part 결과 매핑: "
        "input_part_num=%s, mapped_part_num=%s, name=%s, image_url=%s",
        raw_part_num,
        result["part_num"],
        result["part_name"],
        part.image_url,
    )

    return result


def build_brick_table_html(
    brick_rows: List[Dict[str, Any]],
    client: Optional[RebrickableClient] = None,
) -> str:
    logger.info(
        "[brick_table] 브릭/부품 제안 테이블 생성 시작. 입력 행 수: %d",
        len(brick_rows),
    )

    table_html_parts: List[str] = []
    table_html_parts.append(
        """
<table style="border-collapse: collapse; width: 100%; table-layout: fixed;">
  <thead>
    <tr>
      <th style="border: 1px solid #ddd; padding: 8px;">부품 종류</th>
      <th style="border: 1px solid #ddd; padding: 8px;">부품 번호</th>
      <th style="border: 1px solid #ddd; padding: 8px;">부품 이름</th>
      <th style="border: 1px solid #ddd; padding: 8px;">이미지</th>
      <th style="border: 1px solid #ddd; padding: 8px;">설명 및 용도</th>
    </tr>
  </thead>
  <tbody>
"""
    )

    for idx, row in enumerate(brick_rows):
        logger.info("[brick_table] 행[%d] 처리 시작: row=%s", idx, row)

        part_type = _safe_get(row, "part_type")
        description = _safe_get(row, "description")

        rebrick_data = _lookup_part_with_rebrickable(row, client)

        part_num = rebrick_data["part_num"]
        part_name = rebrick_data["part_name"]
        image_html = rebrick_data["image_html"]

        part_type_esc = html.escape(part_type)
        part_num_esc = html.escape(part_num)
        part_name_esc = html.escape(part_name)
        description_esc = html.escape(description)

        row_html = f"""
    <tr>
      <td style="border: 1px solid #ddd; padding: 8px;">{part_type_esc}</td>
      <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{part_num_esc}</td>
      <td style="border: 1px solid #ddd; padding: 8px;">{part_name_esc}</td>
      <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{image_html}</td>
      <td style="border: 1px solid #ddd; padding: 8px;">{description_esc}</td>
    </tr>
"""
        table_html_parts.append(row_html)

        logger.info(
            "[brick_table] 행[%d] 최종 테이블 데이터: "
            "part_type=%s, part_num=%s, part_name=%s, description=%s",
            idx,
            part_type,
            part_num,
            part_name,
            description,
        )

    table_html_parts.append("  </tbody>\\n</table>\\n")
    full_html = "".join(table_html_parts)

    logger.info("[brick_table] 브릭/부품 제안 테이블 생성 완료. HTML 길이=%d", len(full_html))

    return full_html
