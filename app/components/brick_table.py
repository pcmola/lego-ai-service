import re
from typing import List, Dict, Any

from utils.rebrickable_client import RebrickableClient


def build_brick_table_html(
    rows: List[Dict[str, Any]],
    client: RebrickableClient,
) -> str:
    """
    브릭/부품 제안 리스트를 받아 Rebrickable API로 이름/이미지를 채운 HTML 테이블 생성.

    강제 규칙
    ----------
    - 한 행에 여러 번호("3001, 3003")가 들어오면 각각 별도 행으로 분할
    - 컬럼 의미 고정:
        부품 종류 | 부품 번호 | 부품 이름 | 이미지 | 설명 및 용도
    - 최종 '부품 번호' 셀에는 **항상 3~6자리 숫자(+선택적 알파벳)만** 들어가게 강제
      (예: "3001 회색" → "3001", "3001c, 3003c" → 각각 "3001c", "3003c")
    """

    html_rows: List[str] = []

    qty_words = {"다수", "소량", "적당량", "많이", "적게", "여러 개", "여러개", "다양한"}

    for base_row in rows:
        base_part_type = (base_row.get("part_type") or "").strip()
        base_raw_part_num = (base_row.get("part_num") or "").strip()
        base_description = (base_row.get("description") or "").strip()

        # --------------------------------------------------
        # 0) "한 행에 여러 번호"가 들어온 경우 분할
        # --------------------------------------------------
        multi_numbers = re.findall(r"\b(\d{3,6}[a-zA-Z]?)\b", base_raw_part_num)
        is_pure_number_list = (
            len(multi_numbers) >= 2
            and re.sub(r"[0-9a-zA-Z ,]", "", base_raw_part_num).strip() == ""
        )

        if is_pure_number_list:
            row_variants = [
                (base_part_type, num, base_description) for num in multi_numbers
            ]
        else:
            row_variants = [
                (base_part_type, base_raw_part_num, base_description),
            ]

        # --------------------------------------------------
        # 각 변형 행 처리
        # --------------------------------------------------
        for part_type, raw_part_num, description in row_variants:
            quantity_info = ""

            # 1) part_type 가 사실상 "부품 번호"인 경우 감지해서 스왑
            part_type_looks_like_num = bool(
                re.fullmatch(r"\d{3,6}[a-zA-Z]?", part_type)
            )
            part_num_looks_like_quantity = (
                raw_part_num in qty_words
                or bool(re.fullmatch(r"[0-9]{1,2}", raw_part_num))
            )

            if part_type_looks_like_num and (not raw_part_num or part_num_looks_like_quantity):
                raw_part_num, quantity_info, part_type = part_type, raw_part_num, ""

            # 2) raw_part_num 에서 번호/색상 분리
            num_match = re.search(r"\b(\d{3,6}[a-zA-Z]?)\b", raw_part_num)
            if num_match:
                part_num = num_match.group(1)
                color_info = raw_part_num.replace(part_num, "").strip(" ,")
            else:
                part_num = ""
                color_info = raw_part_num

            # 색상 → 설명
            if color_info and color_info not in ("-", "0"):
                if description:
                    description = f"{description} (색상: {color_info})"
                else:
                    description = f"색상: {color_info}"

            # 수량 → 설명
            if quantity_info and quantity_info not in ("-", "0"):
                if description:
                    description = f"{description} (수량: {quantity_info})"
                else:
                    description = f"수량: {quantity_info}"

            # 3) Rebrickable 조회
            hint_text_parts = [part_type, description]
            hint_text = " ".join([t for t in hint_text_parts if t]).strip()

            part_data = client.resolve_part(part_num, hint_text)

            if part_data:
                part_name = (part_data.get("name") or "").strip()
                img_url = (part_data.get("part_img_url") or "").strip()
                resolved_part_num = (part_data.get("part_num") or "").strip()
            else:
                part_name = ""
                img_url = ""
                resolved_part_num = ""

            # 4) 최종 '부품 번호' 셀 값 강제 정리
            raw_display_source = resolved_part_num or part_num or ""
            if raw_display_source:
                m = re.search(r"\b(\d{3,6}[a-zA-Z]?)\b", raw_display_source)
                display_part_num = m.group(1) if m else "-"
            else:
                display_part_num = "-"

            # 5) 이미지 셀
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
                  <td style="padding: 8px; text-align:left;">{part_type}</td>
                  <td style="padding: 8px; text-align:center; white-space:nowrap;">{display_part_num}</td>
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
