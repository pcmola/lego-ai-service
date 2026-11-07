"""층별 조립 도안 (2D 평면도)

최종 설계 가이드 → (LLM, 구조화 출력) 층별 브릭 좌표 → 검증(범위/겹침/지지) → SVG 렌더링

좌표계: 위에서 내려다본 격자, 단위 = 스터드(돌기) 1칸
  x: 왼쪽 → 오른쪽, y: 위 → 아래, 브릭은 (x, y)에서 시작해 가로 w, 세로 d 칸 차지
  layer level 1 = 바닥, 한 층 = 브릭 1단 높이
"""
import html
import logging
from collections import Counter
from typing import Dict, List, Literal, Set, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from utils.config import get_llm_for_agent

logger = logging.getLogger(__name__)

MAX_SIZE = 16     # 바닥 최대 16x16 스터드
MAX_LAYERS = 8
MAX_BRICKS = 150

# ------------------------------------------------------------
# 색상 (레고 계열 대표색)
# ------------------------------------------------------------
COLORS: Dict[str, Tuple[str, str]] = {
    "white": ("#F4F4F4", "흰색"),
    "light_gray": ("#A0A5A9", "밝은 회색"),
    "dark_gray": ("#6C6E68", "진한 회색"),
    "black": ("#1B2A34", "검정"),
    "red": ("#C91A09", "빨강"),
    "dark_red": ("#720E0F", "진한 빨강"),
    "orange": ("#FE8A18", "주황"),
    "yellow": ("#F2CD37", "노랑"),
    "lime": ("#BBE90B", "연두"),
    "green": ("#237841", "초록"),
    "sand_green": ("#A0BCAC", "샌드 그린"),
    "blue": ("#0055BF", "파랑"),
    "medium_blue": ("#5A93DB", "중간 파랑"),
    "dark_blue": ("#0A3463", "진한 파랑"),
    "tan": ("#E4CD9E", "황갈색"),
    "brown": ("#583927", "갈색"),
    "pink": ("#FC97AC", "분홍"),
    "purple": ("#81007B", "보라"),
    "trans_clear": ("#E8F4F8", "투명"),
    "trans_blue": ("#AEEFEC", "투명 파랑"),
}

ColorName = Literal[
    "white", "light_gray", "dark_gray", "black", "red", "dark_red", "orange", "yellow",
    "lime", "green", "sand_green", "blue", "medium_blue", "dark_blue", "tan", "brown",
    "pink", "purple", "trans_clear", "trans_blue",
]
KIND_KO = {"brick": "브릭", "plate": "플레이트", "tile": "타일", "slope": "경사", "round": "원형", "other": "기타"}


# ------------------------------------------------------------
# 구조화 출력 스키마
# ------------------------------------------------------------
class Brick(BaseModel):
    x: int = Field(description="왼쪽 위 모서리 x (0부터)")
    y: int = Field(description="왼쪽 위 모서리 y (0부터)")
    w: int = Field(description="가로 스터드 수 (1~8)")
    d: int = Field(description="세로 스터드 수 (1~8)")
    color: ColorName
    kind: Literal["brick", "plate", "tile", "slope", "round", "other"]
    part: str = Field(description="Rebrickable/LEGO 부품 번호 (예: 3001). 모르면 빈 문자열")


class Layer(BaseModel):
    level: int = Field(description="1 = 바닥층")
    note: str = Field(description="이 층에서 만드는 것 (한국어 한 줄)")
    bricks: List[Brick]


class Blueprint(BaseModel):
    title: str = Field(description="도안 제목 (한국어)")
    width: int = Field(description=f"바닥 가로 스터드 수 (4~{MAX_SIZE})")
    depth: int = Field(description=f"바닥 세로 스터드 수 (4~{MAX_SIZE})")
    layers: List[Layer]


_SYSTEM = f"""당신은 레고 조립 도안 설계자입니다.
주어진 레고 설계 가이드를 바탕으로, 실제로 쌓아 올릴 수 있는 '층별 배치도'를 만드세요.

[좌표 규칙]
- 위에서 내려다본 격자, 단위는 스터드 1칸. x는 왼쪽→오른쪽, y는 위→아래, 0부터 시작.
- 브릭은 (x, y)에서 시작해 가로 w, 세로 d 칸을 차지. 반드시 0 ≤ x, x+w ≤ width, 0 ≤ y, y+d ≤ depth.
- 바닥 크기 width, depth 는 각각 {MAX_SIZE} 이하. 층은 {MAX_LAYERS}개 이하. 전체 브릭 {MAX_BRICKS}개 이하.
- level 1 이 바닥층. 한 층은 브릭 1단 높이.

[조립 규칙]
- 같은 층의 브릭끼리 겹치면 안 됩니다.
- 2층부터 모든 브릭은 바로 아래층 브릭 위에 최소 1칸 이상 걸쳐 있어야 합니다(공중에 뜨면 안 됨).
- 위아래 층의 이음새가 엇갈리도록(벽돌 쌓기처럼) 배치해 튼튼하게 만드세요.
- 표준 크기만 사용: 1x1, 1x2, 1x3, 1x4, 1x6, 1x8, 2x2, 2x3, 2x4, 2x6, 2x8 (가로/세로 회전 가능).

[내용 규칙]
- 가이드의 '브릭/부품 제안' 표에 있는 부품과 색을 우선 사용하고, part 에 부품 번호를 적으세요(모르면 빈 문자열).
- 작품이 크면 핵심 형태만 살린 축소 모형(미니 버전)으로 설계하세요.
- 각 층 note 에 그 층에서 무엇을 만드는지 한국어 한 줄로 적으세요."""


def generate_blueprint(answer: str) -> Blueprint:
    llm = get_llm_for_agent("BLUEPRINT")
    structured = llm.with_structured_output(Blueprint, method="json_schema", strict=True)
    return structured.invoke(
        [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content="## 레고 설계 가이드\n" + answer[:12000]),
        ]
    )


# ------------------------------------------------------------
# 검증
# ------------------------------------------------------------
def _cells(b: Brick) -> Set[Tuple[int, int]]:
    return {(b.x + i, b.y + j) for i in range(b.w) for j in range(b.d)}


def validate_blueprint(bp: Blueprint) -> Tuple[Blueprint, List[Dict], List[str]]:
    """
    범위 밖/겹침 브릭은 제거, 떠 있는 브릭은 표시만.
    반환: (정리된 도안, 층별 렌더링 정보, 경고 목록)
    """
    width = max(1, min(bp.width, MAX_SIZE))
    depth = max(1, min(bp.depth, MAX_SIZE))
    warnings: List[str] = []
    if (width, depth) != (bp.width, bp.depth):
        warnings.append(f"바닥 크기를 {bp.width}x{bp.depth} → {width}x{depth} 로 제한했습니다.")

    layers = sorted(bp.layers, key=lambda l: l.level)[:MAX_LAYERS]
    out_of_bounds = overlaps = floating = 0
    total = 0
    render_layers: List[Dict] = []
    below: Set[Tuple[int, int]] = set()

    for idx, layer in enumerate(layers):
        occupied: Set[Tuple[int, int]] = set()
        kept: List[Dict] = []
        for b in layer.bricks:
            if total >= MAX_BRICKS:
                break
            if b.w < 1 or b.d < 1 or b.x < 0 or b.y < 0 or b.x + b.w > width or b.y + b.d > depth:
                out_of_bounds += 1
                continue
            cells = _cells(b)
            if cells & occupied:
                overlaps += 1
                continue
            occupied |= cells
            is_floating = idx > 0 and not (cells & below)
            floating += is_floating
            kept.append({"brick": b, "floating": is_floating})
            total += 1
        render_layers.append({"level": idx + 1, "note": layer.note, "bricks": kept, "below": below})
        below = occupied

    if out_of_bounds:
        warnings.append(f"격자 밖으로 나간 브릭 {out_of_bounds}개를 제외했습니다.")
    if overlaps:
        warnings.append(f"같은 층에서 겹친 브릭 {overlaps}개를 제외했습니다.")
    if floating:
        warnings.append(f"아래층에 받쳐지지 않은(떠 있는) 브릭 {floating}개가 있습니다. 빨간 점선으로 표시했습니다.")

    bp_clean = Blueprint(title=bp.title, width=width, depth=depth, layers=layers)
    return bp_clean, render_layers, warnings


# ------------------------------------------------------------
# 렌더링 (HTML + SVG)
# ------------------------------------------------------------
def _layer_svg(layer: Dict, width: int, depth: int, cell: int) -> str:
    W, H = width * cell, depth * cell
    parts = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">',
             f'<rect width="{W}" height="{H}" fill="#FAFAF7"/>']
    # 아래층 위치(희미하게) → 정렬 참고용
    for (cx, cy) in layer["below"]:
        parts.append(f'<rect x="{cx*cell}" y="{cy*cell}" width="{cell}" height="{cell}" fill="#000" fill-opacity="0.07"/>')
    # 격자
    for i in range(width + 1):
        parts.append(f'<line x1="{i*cell}" y1="0" x2="{i*cell}" y2="{H}" stroke="#E2E2DC" stroke-width="1"/>')
    for j in range(depth + 1):
        parts.append(f'<line x1="0" y1="{j*cell}" x2="{W}" y2="{j*cell}" stroke="#E2E2DC" stroke-width="1"/>')
    # 브릭
    for item in layer["bricks"]:
        b: Brick = item["brick"]
        fill = COLORS.get(b.color, ("#999", b.color))[0]
        x, y, w, h = b.x * cell, b.y * cell, b.w * cell, b.d * cell
        stroke = 'stroke="#D62828" stroke-width="2.5" stroke-dasharray="5 3"' if item["floating"] \
            else 'stroke="#00000066" stroke-width="1.5"'
        title = html.escape(f"{b.w}x{b.d} {KIND_KO.get(b.kind, b.kind)} {COLORS.get(b.color, ('', b.color))[1]}"
                            + (f" #{b.part}" if b.part else "") + (" (떠 있음)" if item["floating"] else ""))
        parts.append(f'<g><title>{title}</title>'
                     f'<rect x="{x+1}" y="{y+1}" width="{w-2}" height="{h-2}" rx="2" fill="{fill}" {stroke}/>')
        if b.kind != "tile":
            r = cell * 0.27
            for i in range(b.w):
                for j in range(b.d):
                    cx, cy = x + (i + 0.5) * cell, y + (j + 0.5) * cell
                    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="#00000033" stroke-width="1"/>')
        parts.append('</g>')
    parts.append('</svg>')
    return "".join(parts)


def render_blueprint_html(bp: Blueprint, render_layers: List[Dict]) -> str:
    cell = max(12, min(22, 300 // max(bp.width, bp.depth)))
    cards = []
    for layer in render_layers:
        n = len(layer["bricks"])
        cards.append(
            '<div class="card">'
            f'<div class="hd"><b>{layer["level"]}층</b><span>{n}개</span></div>'
            f'<div class="note">{html.escape(layer["note"] or "")}</div>'
            f'{_layer_svg(layer, bp.width, bp.depth, cell)}'
            '</div>'
        )

    # 부품 요약
    counter: Counter = Counter()
    for layer in render_layers:
        for item in layer["bricks"]:
            b: Brick = item["brick"]
            counter[(b.part, f"{min(b.w, b.d)}x{max(b.w, b.d)}", b.kind, b.color)] += 1
    rows = []
    for (part, size, kind, color), cnt in sorted(counter.items(), key=lambda kv: -kv[1]):
        hexc, ko = COLORS.get(color, ("#999", color))
        rows.append(
            f'<tr><td><span class="sw" style="background:{hexc}"></span>{ko}</td>'
            f'<td>{size} {KIND_KO.get(kind, kind)}</td><td>{html.escape(part) or "-"}</td><td class="r">{cnt}</td></tr>'
        )
    total = sum(counter.values())

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;font-family:"Pretendard","Noto Sans KR",system-ui,sans-serif;color:#222;background:#fff}}
.meta{{font-size:13px;color:#666;margin:2px 0 10px}}
.grid{{display:flex;flex-wrap:wrap;gap:12px}}
.card{{border:1px solid #E5E5E0;border-radius:10px;padding:10px;background:#fff}}
.hd{{display:flex;justify-content:space-between;font-size:14px;margin-bottom:2px}}
.hd span{{color:#888;font-size:12px}}
.note{{font-size:12px;color:#555;margin-bottom:6px;max-width:{bp.width*cell}px}}
table{{border-collapse:collapse;font-size:13px;margin-top:16px;min-width:360px}}
th,td{{border-bottom:1px solid #EEE;padding:5px 10px;text-align:left}} th{{color:#666;font-weight:600}}
td.r{{text-align:right}} .sw{{display:inline-block;width:12px;height:12px;border-radius:3px;border:1px solid #0003;margin-right:6px;vertical-align:-1px}}
</style></head><body>
<div class="meta">{html.escape(bp.title)} · 바닥 {bp.width}x{bp.depth} 스터드 · {len(render_layers)}층 · 브릭 {total}개
 · 회색 음영 = 바로 아래층 위치</div>
<div class="grid">{''.join(cards)}</div>
<table><tr><th>색상</th><th>크기/종류</th><th>부품 번호</th><th class="r">수량</th></tr>{''.join(rows)}</table>
</body></html>"""


def build_blueprint(answer: str) -> Dict:
    """생성 → 검증 → 렌더링. 반환: {"html", "height", "warnings", "summary"}"""
    bp = generate_blueprint(answer)
    bp, render_layers, warnings = validate_blueprint(bp)
    cell = max(12, min(22, 300 // max(bp.width, bp.depth)))
    card_w = bp.width * cell + 22
    per_row = max(1, 900 // card_w)
    rows = -(-len(render_layers) // per_row)
    n_parts = len({(i["brick"].part, i["brick"].w, i["brick"].d, i["brick"].color)
                   for l in render_layers for i in l["bricks"]})
    height = 40 + rows * (bp.depth * cell + 70) + 60 + n_parts * 28
    total = sum(len(l["bricks"]) for l in render_layers)
    logger.info("[blueprint] %s %dx%d, %d층, 브릭 %d개, 경고 %s", bp.title, bp.width, bp.depth,
                len(render_layers), total, warnings)
    return {
        "html": render_blueprint_html(bp, render_layers),
        "height": min(height, 1600),
        "warnings": warnings,
        "summary": f"{bp.width}x{bp.depth} · {len(render_layers)}층 · 브릭 {total}개",
    }
