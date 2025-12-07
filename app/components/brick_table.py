import re
from typing import List, Dict, Any

from utils.rebrickable_client import RebrickableClient


PART_NUM_PATTERN = re.compile(r"\b(\d{3,6}[a-zA-Z]?)\b")
URL_PATTERN = re.compile(r"https?://\S+")


def _extract_part_num(type_raw: str, num_raw: str) -> (str, str, str):
    """
    part_type, part_num 두 칸을 같이 보고
    - 첫 번째로 발견된 3~6자리(+알파벳) 토큰을 부품 번호로 사용
    - 해당 번호는 원 문자열에서 제거하고 남은 텍스트는 색상/기타 정보로 반환
    """
    text_for_num = f"{num_raw} {type_raw}".strip()

    m = PART_NUM_PATTERN.search(text_for_num)
    if not m:
        return "", type_raw.strip(), num_raw.strip()

    part_num = m.group(1)

    # type_raw / num_raw 에서 번호 제거
    type_left = PART_NUM_PATTERN.sub("", type_raw).strip(" ,")
    num_left = PART_NUM_PATTERN.sub("", num_raw).strip(" ,")

    # 남은 건 색상/수량 등의 추가 정보로 쓰기
    extra = " ".join([s for s in [type_left, num_left] if s]).strip()

    return part_num, type_left, extra


def _clean_description(desc: str, extra_info: str) -> str:
    """설명 텍스트에서 URL 제거 + 색상/수량 같은 추가 정보 합치기"""
    desc = (desc or "").strip()

    # 설명에 들어온 URL 제거
    if desc:
        desc = URL_PATTERN.sub("", desc).strip()

    # 추가 정보 붙이기
    if extra_info:
        if desc:
            desc = f"{desc} ({extra_info})"
        else:
            desc = extra_info

    return desc or "-"


def build_brick_table_html(
    rows: List[Dict[str, Any]],
    client: RebrickableClient,
) -> str:
    """
    브릭/부품 제안 리스트를 받아 Rebrickable API로 이름/이미지를 채운 HTML 테이블 생성.

    최종 표 의미는 항상:
      부품 종류 | 부품 번호 | 부품 이름 | 이미지 | 설명 및 용도

    - 부품 번호는 3~6자리(+선택 알파벳) 토큰만 허용
    - 부품 종류에 숫자만 들어온 경우 → 번호로 인식하고 종류는 비움
    - 설명 안에 들어온 URL 은 모두 제거
    """

    html_rows: List[str] = []

    for row in rows:
        type_raw = (row.get("part_type") or "").strip()
        num_raw = (row.get("part_num") or "").strip()
        desc_raw = (row.get("description") or "").strip()

        # 1) 부품 번호 추출 (type/num 칸을 같이 보고 숫자 하나 뽑기)
        part_num, type_text, extra_info = _extract_part_num(type_raw, num_raw)

        # 2) 설명 정리 (URL 제거 + 색상/수량 정보 합치기)
        description = _clean_description(desc_raw, extra_info)

        # 3) Rebrickable 조회 (번호가 있으면 우선, 없으면 타입/설명으로 텍스트 검색)
        hint_text = " ".join([type_text, description]).strip()
        part_data = client.resolve_part(part_num, hint_text)

        if part_data:
            part_name = (part_data.get("name") or "").strip()
            img_url = (part_data.get("part_img_url") or "").strip()
            # Rebrickable에서 다시 번호를 가져와서 확정
            resolved_part_num = (part_data.get("part_num") or "").strip()
        else:
            part_name = ""
            img_url = ""
            resolved_part_num = part_num

        # 4) 최종 부품 번호 셀: 순수 번호만 남기기
        display_num = "-"
        source_for_num = resolved_part_num or part_num or ""
        if source_for_num:
            m = PART_NUM_PATTERN.search(source_for_num)
            if m:
                display_num = m.group(1)

        # 5) 부품 종류 셀
        #    - 타입 텍스트가 없고, Rebrickable 이름이 있으면 종류 대신 이름의 짧은 버전 사용
        display_type = type_text
        if not display_type and part_name:
            display_type = part_name

        # 6) 이미지 셀
        if img_url:
            img_html = (
                f"<img src='{img_url}' alt='part image' "
                f"style='max-width:80px; height:auto;' />"
            )
        else:
            img_html = "-"

        html_rows.append(
            f"""
            <tr>
              <td style="padding: 8px; text-align:left;">{display_type or "-"}</td>
              <td style="padding: 8px; text-align:center; white-space:nowrap;">{display_num}</td>
              <td style="padding: 8px; text-align:left;">{part_name or "-"}</td>
              <td style="padding: 8px; text-align:center;">{img_html}</td>
              <td style="padding: 8px; text-align:left;">{description}</td>
            </tr>
            """
        )

    table_html = f"""
    <div style="width: 100%; overflow-x: auto;">
      <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;" border="1">
        <thead>
          <tr style="background-color:#f5f5f5;">
            <th style="padding: 8px;">부품 종류</th>
            <th style="padding: 8px;">부품 번호</th>
            <th style="padding: 8px;">부품 이름</th>
            <th style="padding: 8px;">이미지</th>
            <th style="padding: 8px;">설명 및 용도</th>
          </tr>
        </thead>
        <tbody>
          {''.join(html_rows)}
        </tbody>
      </table>
    </div>
    """
    return table_html
