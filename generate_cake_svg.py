# -*- coding: utf-8 -*-
"""GitHub 프로필에 붙이는 딸기 케이크 잔디 카드를 SVG로 만든다.
Build the strawberry-cake contribution card for a GitHub profile README, as SVG.

GitHub Actions가 30분마다 이 스크립트를 돌려 cake.svg 를 갱신하고 커밋한다.
기여 내용이 그대로면 파일을 건드리지 않아 쓸데없는 커밋이 쌓이지 않는다.
서버도 토큰도 필요 없다. 데이터는 공개 프로필 페이지에서 읽는다.
A GitHub Action runs this every 30 minutes to refresh and commit cake.svg. An
unchanged card is left untouched, so no pointless commits pile up.
No server and no token are needed; the data comes from the public profile page.

배치: 왼쪽에 이름과 통계표, 오른쪽에 케이크 격자와 범례.
Layout: name and stats on the left, the cake grid and its legend on the right.

사용법 / usage:
    python generate_cake_svg.py --user JuHuiHeo --out cake.svg
"""

import argparse
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

# ------------------------------------------------- 치수 / metrics
TW, TH, SL = 15.0, 7.5, 6.4     # 타일 반너비 · 반높이 · 층 높이 / tile half width, half height, layer
# 원본 디자인처럼 칸끼리 딱 붙인다. 1보다 작게 하면 칸 사이에 틈이 생겨
# 기여가 없는 구간에서 날짜 경계가 드러난다.
# Tiles sit edge to edge as in the original design. Set this below 1 to open a
# hairline gap, which makes day boundaries visible across quiet stretches.
GAP = 1.0
FW, FH = TW * GAP, TH * GAP     # 도형의 반너비 · 반높이 / drawn half width and half height
ROWS = 7                        # 요일 / days per week
PAD = 28
CAKE_UP = 36                    # 4단 케이크가 자리 위로 솟는 높이 / how far a level-4 cake rises

# 왼쪽 기둥: 이름과 통계표 / left column: the name and the stats table
CARD_W, CARD_H = 230, 138
CARD_Y = 104
COL_GAP = 26                    # 왼쪽 기둥과 격자 사이 / gap between the column and the grid
RIGHT_MIN = 380                 # 오른쪽 영역 최소 너비 / minimum width of the right side

# ------------------------------------------------- 색 / palette
BG = "#FFF5F6"
CARD = "#FFFFFF"
BORDER = "#F6D6DD"
FG = "#5A3A40"
DIM = "#9A6B74"
ACCENT = "#E23A4C"

LAYERS = [{"l": "#EAC98D", "r": "#F7DFB0"},    # 시트 / sponge
          {"l": "#F0DED1", "r": "#FDF3EA"}]    # 크림 / cream
TOP = "#FFFAF5"
JAM = {"l": "#E5738D", "r": "#F594A9"}
PLATE = {"t": "#FBE9DE", "l": "#EAD3C6", "r": "#F5E1D5"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# 프로필 카드는 누가 볼지 모르니, 어느 OS에나 있는 글꼴만 쓴다
# Anyone may view a profile card, so stick to fonts every OS has
FONT = "Segoe UI,Helvetica,Arial,sans-serif"

# 딸기와 크림은 원본 디자인의 경로를 그대로 쓴다 (SVG라 곡선을 변환할 필요가 없다)
# The berry and cream keep the original design's paths - being SVG, no flattening is needed
BERRY = (
    '<path d="M-4.2 -4.6 C-4.2 -7.4 -2.7 -9.5 -1.3 -10.5 C-0.5 -11.1 0.5 -11.1 1.3 -10.5 '
    'C2.7 -9.5 4.2 -7.4 4.2 -4.6 C4.2 -1.5 2.4 0.6 0 0.6 C-2.4 0.6 -4.2 -1.5 -4.2 -4.6 Z" fill="#E23A4C"/>'
    '<path d="M3.3 -6.6 C4.1 -4.8 4.4 -2.2 3.1 -0.6 C2.3 0.2 1.1 0.6 0.1 0.6 C2.3 -0.2 3.7 -3 3.3 -6.6 Z" '
    'fill="#C62D40"/>'
    '<path d="M-2.7 -5.2 C-2.9 -7.2 -1.7 -8.8 -0.6 -9.6 C-1.6 -7.8 -2 -6.5 -1.9 -4.4 '
    'C-2.3 -4.6 -2.6 -4.8 -2.7 -5.2 Z" fill="#F2707F"/>'
)
TOPPER = (
    '<path d="M-5.3 0.3 C-5.3 -2.4 -3.2 -4.8 0 -4.8 C3.2 -4.8 5.3 -2.4 5.3 0.3 '
    'C3.6 1.7 -3.6 1.7 -5.3 0.3 Z" fill="#FBF0E6"/>'
    '<g transform="translate(0,-1.2) scale(0.85)">' + BERRY + '</g>'
    '<path d="M-5.3 0.2 C-4.9 -1.7 -3.1 -2.7 0 -2.7 C3.1 -2.7 4.9 -1.7 5.3 0.2 '
    'C3.6 1.7 -3.6 1.7 -5.3 0.2 Z" fill="#FFFCF8"/>'
    '<path d="M3.4 -1.9 C4.5 -1.2 5.1 -0.5 5.3 0.2 C4.6 0.9 3.4 1.3 2.2 1.5 '
    'C3.3 0.4 3.6 -0.8 3.4 -1.9 Z" fill="#EFE0D3"/>'
    '<path d="M-1.4 -2.5 C-2.9 -2.2 -4 -1.5 -4.6 -0.6 C-4.9 -0.2 -5.1 0.2 -5.2 0.6 '
    'C-5.4 -0.5 -4.8 -1.5 -3.6 -2.1 C-2.9 -2.4 -2.2 -2.5 -1.4 -2.5 Z" fill="#FFFFFF"/>'
    '<ellipse cx="-3.1" cy="-1.9" rx="1.15" ry="0.75" fill="#FFFDFA" transform="rotate(-18 -3.1 -1.9)"/>'
    '<ellipse cx="3.1" cy="-2.1" rx="1.1" ry="0.72" fill="#FFFDFA" transform="rotate(16 3.1 -2.1)"/>'
)


def fetch_contributions(username):
    """공개 프로필의 잔디 페이지에서 (칸 목록, 총 기여수)를 읽는다.
    Read (cells, total) from the public contributions page."""
    url = "https://github.com/users/%s/contributions" % urllib.request.quote(username)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    })
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

    tips = dict(re.findall(
        r'<tool-tip[^>]*for="(contribution-day-component-[\d-]+)"[^>]*>(.*?)</tool-tip>',
        html, re.S))

    cells = []
    for tag in re.findall(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', html):
        date = re.search(r'data-date="([\d-]+)"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        cid = re.search(r'id="(contribution-day-component-[\d-]+)"', tag)
        if not (date and level and cid):
            continue
        # id 끝의 두 숫자가 (요일, 몇 번째 주)다 / the trailing numbers are (weekday, week)
        row, col = cid.group(1).rsplit("-", 2)[-2:]
        tip = re.sub(r"\s+", " ", tips.get(cid.group(1), "")).strip()
        num = re.match(r"(\d+)", tip)
        cells.append({"date": date.group(1), "level": int(level.group(1)),
                      "row": int(row), "col": int(col),
                      "count": int(num.group(1)) if num else 0})

    total = 0
    m = re.search(r"([\d,]+)\s*contributions?\s*in\s*the\s*last\s*year", html, re.I | re.S)
    if m:
        total = int(m.group(1).replace(",", ""))
    if not cells:
        raise SystemExit("기여 데이터를 찾지 못했습니다 / no contribution data found for %r" % username)
    return cells, total


def n(value):
    """좌표를 짧게. 파일 크기를 줄인다. / Trim coordinates to keep the file small."""
    return ("%.1f" % value).rstrip("0").rstrip(".")


def poly(points, fill):
    return '<polygon points="%s" fill="%s"/>' % (
        " ".join("%s,%s" % (n(x), n(y)) for x, y in points), fill)


def f_left(yy, h):
    return [(-FW, yy), (0, yy + FH), (0, yy + FH + h), (-FW, yy + h)]


def f_right(yy, h):
    return [(0, yy + FH), (FW, yy), (FW, yy + h), (0, yy + FH + h)]


def f_top(yy):
    return [(0, yy - FH), (FW, yy), (0, yy + FH), (-FW, yy)]


def cell_symbol(level):
    """단계 하나짜리 케이크를 원점 기준으로 그린다.
    Draw one cake of the given level, positioned at the origin.

    단계가 다섯 가지뿐이라 <defs>에 한 번만 정의하고 모든 칸이 <use>로 재사용한다.
    There are only five levels, so each is defined once and reused by every cell."""
    if level <= 0:
        yy = -2.2
        return (poly(f_left(yy, 2.2), PLATE["l"]) + poly(f_right(yy, 2.2), PLATE["r"])
                + poly(f_top(yy), PLATE["t"]))

    out = []
    for i in range(1, level + 1):
        yy = -i * SL
        c = LAYERS[(i - 1) % 2]
        out.append(poly(f_left(yy, SL), c["l"]))
        out.append(poly(f_right(yy, SL), c["r"]))
        if i == level:                       # 맨 위 층만 장식 / only the top layer is decorated
            if level >= 3:                   # 잼이 흘러내린다 / jam spills over
                out.append(poly(f_left(yy, 2.8), JAM["l"]))
                out.append(poly(f_right(yy, 2.8), JAM["r"]))
            out.append(poly(f_top(yy), TOP if level >= 2 else c["r"]))
            if level >= 4:                   # 딸기 한 알 / crowned with a strawberry
                out.append('<g transform="translate(0,%s) scale(1.2)">%s</g>'
                           % (n(yy + 2.8), TOPPER))
    return "".join(out)


def layout(weeks):
    """주 수에 맞춰 카드 크기와 각 요소의 자리를 계산한다.
    Work out the card size and where each piece sits, for the requested weeks.

    왼쪽은 이름과 통계표로 폭이 고정이고, 오른쪽 격자만 주 수에 따라 넓어진다.
    The left column is a fixed width; only the grid on the right grows with the weeks."""
    span_w = (weeks - 1 + ROWS - 1) * TW + 2 * FW       # 격자 가로 폭 / grid width
    left_w = PAD + CARD_W + COL_GAP                     # 오른쪽 영역이 시작하는 x / where the right side starts
    right_w = max(span_w, RIGHT_MIN)
    width = left_w + right_w + PAD

    ox = left_w + (right_w - span_w) / 2 + (ROWS - 1) * TW + FW   # 오른쪽 안에서 가운데 / centred on the right
    oy = PAD + CAKE_UP
    month_y = oy + (weeks - 1 + ROWS - 1) * TH + FH + 12
    legend_y = month_y + 46
    legend_cx = left_w + right_w / 2

    height = max(legend_y + FH + PAD, CARD_Y + CARD_H + PAD)
    return {"w": width, "h": int(height), "ox": ox, "oy": oy,
            "month_y": month_y, "legend_y": legend_y, "legend_cx": legend_cx}


def compute_stats(cells):
    """총 기여 · 최고의 날 · 최장 연속. / Total, best day and longest streak."""
    days = sorted((c["date"], c["count"]) for c in cells)
    best = max([v for _, v in days], default=0)
    longest = run = 0
    for _, v in days:
        run = run + 1 if v > 0 else 0
        longest = max(longest, run)
    return sum(v for _, v in days), best, longest


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_svg(username, cells, total, weeks):
    last = max(c["col"] for c in cells)
    first = max(0, last - weeks + 1)
    shown = [dict(c, col=c["col"] - first) for c in cells if c["col"] >= first]
    weeks = max(q["col"] for q in shown) + 1          # 실제로 받은 주 수 / weeks actually present
    _, best, streak = compute_stats(cells)
    L = layout(weeks)

    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img" '
             'aria-label="%s의 기여 그래프를 딸기 케이크로 그린 그림">'
             % (L["w"], L["h"], L["w"], L["h"], esc(username)))
    p.append("<title>%s - contribution cake</title>" % esc(username))
    p.append("<desc>단계가 오를수록 시트와 크림이 쌓이고, 가장 높은 날에는 "
             "크림에 파묻힌 딸기가 올라갑니다. / Cakes rise with each level and the "
             "busiest days are crowned with a cream-nestled strawberry.</desc>")

    # 단계별 케이크를 한 번만 정의 / define each level once
    p.append("<defs>")
    for level in range(5):
        p.append('<g id="L%d">%s</g>' % (level, cell_symbol(level)))
    p.append("</defs>")

    p.append('<rect width="%d" height="%d" rx="16" fill="%s"/>' % (L["w"], L["h"], BG))

    # ---------------- 왼쪽: 이름과 통계표 / left: the name and the stats table
    p.append('<text x="%d" y="44" font-family="%s" font-size="19" font-weight="600" '
             'fill="%s">%s</text>' % (PAD, FONT, FG, esc(username)))
    p.append('<text x="%d" y="64" font-family="%s" font-size="12" fill="%s">'
             '%s contributions in the last year</text>'
             % (PAD, FONT, DIM, "{:,}".format(total)))
    p.append('<text x="%d" y="82" font-family="%s" font-size="10" fill="%s">'
             'last %d weeks shown &#183; updated %s UTC</text>'
             % (PAD, FONT, DIM, weeks,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")))

    p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="%s" '
             'stroke="%s"/>' % (PAD, CARD_Y, CARD_W, CARD_H, CARD, BORDER))
    row_h = CARD_H / 3.0
    for i, (value, label) in enumerate(((total, "Total"), (best, "Best day"),
                                        (streak, "Longest streak"))):
        base = CARD_Y + row_h * i + row_h / 2 + 7
        p.append('<text x="%d" y="%s" font-family="%s" font-size="21" fill="%s">%s</text>'
                 % (PAD + 22, n(base), FONT, ACCENT, "{:,}".format(value)))
        p.append('<text x="%d" y="%s" text-anchor="end" font-family="%s" font-size="11" '
                 'fill="%s">%s</text>' % (PAD + CARD_W - 22, n(base), FONT, DIM, label))
        if i < 2:                                     # 칸 사이 옅은 줄 / a faint rule between rows
            ry = CARD_Y + row_h * (i + 1)
            p.append('<line x1="%d" y1="%s" x2="%d" y2="%s" stroke="%s"/>'
                     % (PAD + 16, n(ry), PAD + CARD_W - 16, n(ry), BORDER))

    # ---------------- 오른쪽: 케이크 격자 / right: the cake grid
    # 뒤쪽 칸부터 그려야 앞의 케이크가 위를 덮는다
    # Draw back to front so nearer cakes overlap the ones behind
    for cell in sorted(shown, key=lambda q: (q["col"] + q["row"], q["col"])):
        bx = L["ox"] + (cell["col"] - cell["row"]) * TW
        by = L["oy"] + (cell["col"] + cell["row"]) * TH
        p.append('<use href="#L%d" x="%s" y="%s"/>' % (cell["level"], n(bx), n(by)))

    # 맨 앞줄 아래에 달이 바뀌는 지점만 / months under the front row, where they change
    last_month = None
    for cell in sorted([q for q in shown if q["row"] == ROWS - 1], key=lambda q: q["col"]):
        month = int(cell["date"][5:7])
        if month != last_month:
            if last_month is not None:
                bx = L["ox"] + (cell["col"] - (ROWS - 1)) * TW
                by = L["oy"] + (cell["col"] + ROWS - 1) * TH
                p.append('<text x="%s" y="%s" text-anchor="middle" font-family="%s" '
                         'font-size="10" fill="%s">%s</text>'
                         % (n(bx), n(by + FH + 12), FONT, DIM, MONTHS[month - 1]))
            last_month = month

    # ---------------- 오른쪽 아래: 단계 범례 / bottom right: the level legend
    x0 = L["legend_cx"] - 80                          # 범례도 오른쪽 영역 가운데 / centred on the right too
    ly = L["legend_y"]
    p.append('<text x="%s" y="%s" text-anchor="end" font-family="%s" font-size="11" '
             'fill="%s">Less</text>' % (n(x0 - 24), n(ly + 4), FONT, DIM))
    for level in range(5):
        p.append('<use href="#L%d" x="%s" y="%s"/>' % (level, n(x0 + level * 40), n(ly)))
    p.append('<text x="%s" y="%s" font-family="%s" font-size="11" fill="%s">More</text>'
             % (n(x0 + 184), n(ly + 4), FONT, DIM))

    p.append("</svg>")
    return "".join(p)


# 갱신 시각만 다른 경우를 걸러내기 위한 자리 / used to ignore a changed timestamp
STAMP_RE = re.compile(r"updated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")


def same_except_stamp(a, b):
    """갱신 시각을 빼고 같은 그림인지 본다.
    Compare two cards ignoring their timestamp.

    자주 돌릴수록 시각만 바뀐 파일이 매번 커밋돼 기록이 지저분해진다.
    기여 내용이 그대로면 파일을 아예 건드리지 않아 커밋도 생기지 않게 한다.
    Running often would otherwise commit a new timestamp every time and bloat the
    history, so an unchanged card is left untouched and git sees nothing to commit."""
    return STAMP_RE.sub("", a) == STAMP_RE.sub("", b)


def main():
    ap = argparse.ArgumentParser(description="GitHub 기여 그래프를 딸기 케이크 SVG로 만든다")
    ap.add_argument("--user", required=True, help="GitHub 아이디 / GitHub username")
    ap.add_argument("--out", default="cake.svg", help="저장할 파일 / output file")
    ap.add_argument("--weeks", type=int, default=18,
                    help="보여줄 주 수 (기본 18, 위젯과 동일) / weeks to show")
    args = ap.parse_args()

    cells, total = fetch_contributions(args.user)
    svg = build_svg(args.user, cells, total, args.weeks)

    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            if same_except_stamp(f.read(), svg):
                print("기여 내용이 그대로여서 파일을 그대로 둡니다 / unchanged, left as is")
                return

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print("%s 생성 완료 / wrote %s (%.1f KB, %d일치 / %d days)"
          % (args.out, args.out, len(svg.encode("utf-8")) / 1024, len(cells), len(cells)))


if __name__ == "__main__":
    sys.exit(main())
