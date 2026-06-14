# -*- coding: utf-8 -*-
"""시스템 아키텍처 단독 PPT (편집 가능 도형) — 엔진-기능 매핑 + 큰 폰트."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

C = lambda h: RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
JB_BLUE = C('00529b'); JB_DARK = C('003a6e'); INK = C('1a1d21'); MUTED = C('5b6470')
WHITE = C('ffffff'); LINE = C('cdd5de'); TEALc = C('0f9d58'); PURPc = C('5b3bbf')
SLATE = C('5b6470'); AMBER = C('c78a06'); GREYc = C('6b7480')
GREY_T = C('eef1f5'); TEAL_T = C('e7f6ee'); PURP_T = C('efeaff')

prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
s = prs.slides.add_slide(prs.slide_layouts[6]); I = Inches


def settxt(tf, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, m=0.05):
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = Inches(m); tf.margin_right = Inches(m)
    tf.margin_top = Inches(0.01); tf.margin_bottom = Inches(0.01)
    f = True
    for ln in runs:
        p = tf.paragraphs[0] if f else tf.add_paragraph(); f = False
        p.alignment = align; p.space_after = Pt(0); p.space_before = Pt(0); p.line_spacing = 1.0
        for t, sz, b, col in ln:
            r = p.add_run(); r.text = t; r.font.size = Pt(sz); r.font.bold = b
            r.font.color.rgb = col; r.font.name = 'Malgun Gothic'


def shp(kind, x, y, w, h, runs, fill, line=LINE, lw=0.75, align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE, m=0.06):
    sp = s.shapes.add_shape(kind, x, y, w, h); sp.shadow.inherit = False
    if fill is None: sp.fill.background()
    else: sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None: sp.line.fill.background()
    else: sp.line.color.rgb = line; sp.line.width = Pt(lw)
    if runs: settxt(sp.text_frame, runs, align, anchor, m=m)
    return sp


def box(x, y, w, h, runs, fill, **k):
    return shp(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, runs, fill, **k)


def tbox(x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(x, y, w, h); settxt(tb.text_frame, runs, align, anchor, m=0); return tb


def rarrow(x, y, w, h, lab=''):
    shp(MSO_SHAPE.RIGHT_ARROW, x, y, w, h, [], C('8aa0b5'), line=None)
    if lab:
        tbox(x - I(0.35), y - I(0.32), w + I(0.7), I(0.26), [[(lab, 9.5, True, MUTED)]], align=PP_ALIGN.CENTER)


def darrow(xc, y, h, lab=''):
    shp(MSO_SHAPE.DOWN_ARROW, xc - I(0.14), y, I(0.28), h, [], C('8aa0b5'), line=None)
    if lab:
        tbox(xc + I(0.2), y, I(2.5), h, [[(lab, 9.5, True, MUTED)]], anchor=MSO_ANCHOR.MIDDLE)


# 제목
tbox(I(0.45), I(0.20), I(11), I(0.5), [[('JB 준법 코파일럿 - 시스템 아키텍처', 25, True, JB_DARK)]])
tbox(I(0.47), I(0.76), I(12.4), I(0.3),
     [[('사용자 · 프론트엔드 · 백엔드 API · AI Agent/모델 · DB/외부연동 - 전 과정 온프레미스 · 휴먼인더루프', 12, False, MUTED)]])
shp(MSO_SHAPE.RECTANGLE, I(0.45), I(1.12), I(12.43), Pt(2.5), [], JB_BLUE, line=None)

# 사용자
ux, uy, uw, uh = I(0.45), I(1.78), I(2.1), I(2.45)
box(ux, uy, uw, uh, [], C('f4f6f8'), line=SLATE, lw=1.25)
tbox(ux, uy + I(0.12), uw, I(0.32), [[('[사용자]', 14, True, SLATE)]], align=PP_ALIGN.CENTER)
box(ux + I(0.16), uy + I(0.56), uw - I(0.32), I(0.82),
    [[('마케팅·지점 담당자', 11, True, INK)], [('금융 콘텐츠 초안', 9, False, MUTED)], [('작성(실시간)', 9, False, MUTED)]],
    WHITE, line=LINE, m=0.08)
box(ux + I(0.16), uy + I(1.48), uw - I(0.32), I(0.82),
    [[('준법관리자', 11, True, INK)], [('준법감시부', 9, False, MUTED)], [('검토·승인(HITL)', 9, False, MUTED)]],
    WHITE, line=LINE, m=0.08)
rarrow(I(2.66), I(2.8), I(0.46), I(0.42))

# 프론트엔드
fx, fy, fw, fh = I(3.2), I(1.78), I(2.6), I(2.45)
box(fx, fy, fw, fh, [], C('eafaf0'), line=TEALc, lw=1.25)
tbox(fx, fy + I(0.12), fw, I(0.32), [[('[프론트엔드 / UI]', 13.5, True, TEALc)]], align=PP_ALIGN.CENTER)
tbox(fx, fy + I(0.46), fw, I(0.24), [[('정적 SPA · 바닐라 JS (FastAPI 서빙)', 9, False, MUTED)]], align=PP_ALIGN.CENTER)
for i, u in enumerate(['심의 워크스페이스', '오인 시뮬레이터 *', '준법관리자 승인 뷰', '감사로그 뷰']):
    box(fx + I(0.16), fy + I(0.76) + i * I(0.40), fw - I(0.32), I(0.34),
        [[(u, 10.5, '*' in u, INK)]], WHITE, line=C('bfe6cf'), align=PP_ALIGN.CENTER, m=0.05)
rarrow(I(5.9), I(2.8), I(0.46), I(0.42), 'REST(JSON)')

# 코어 (백엔드 API + AI Agent)
cx, cy, cw, ch = I(6.4), I(1.5), I(6.48), I(4.0)
box(cx, cy, cw, ch, [], C('faf8ff'), line=PURPc, lw=1.25)
ix = cx + I(0.18); iw = cw - I(0.36)
tbox(ix, cy + I(0.13), iw, I(0.30), [[('[백엔드 / Backend]  FastAPI (app/main.py) · 온프레미스', 13, True, JB_BLUE)]])
tbox(ix, cy + I(0.50), iw, I(0.28), [[('AI Agent · Orchestrator - 명시적 파이썬 파이프라인', 12, True, PURPc)]])
stages = [('(1)분류', '결정적', GREYc, GREY_T), ('(2)RAG', 'BGE-m3', TEALc, TEAL_T),
          ('(3)룰엔진', '결정적', GREYc, GREY_T), ('(4)LLM심의', 'Ollama', PURPc, PURP_T),
          ('(5)시뮬레이터', 'Ollama', PURPc, PURP_T), ('(6)리포트', '결정적', GREYc, GREY_T),
          ('(7,8)승인·감사', '결정적', GREYc, GREY_T)]
scw = (int(iw) - int(I(0.05)) * (len(stages) - 1)) // len(stages); sy = cy + I(0.84)
for i, (nm, tag, col, tfill) in enumerate(stages):
    x = ix + i * (scw + int(I(0.05)))
    box(x, sy, scw, I(0.92), [[(nm, 10.5, True, INK)], [(' ', 4, False, INK)], [(tag, 9.5, True, col)]],
        tfill, line=col, align=PP_ALIGN.CENTER, m=0.03)
    if i < len(stages) - 1:
        tbox(x + scw - I(0.02), sy, I(0.1), I(0.92), [[('>', 11, True, MUTED)]],
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
box(ix, cy + I(1.86), iw, I(0.48),
    [[('* 준법 오토파일럿', 11.5, True, PURPc), ('  판단->고쳐쓰기->재심의 자율 개선 루프 (Ollama)', 10, False, MUTED)]],
    PURP_T, line=PURPc, align=PP_ALIGN.LEFT, m=0.14)
tbox(ix, cy + I(2.44), iw, I(0.26), [[('[엔진] 어느 모델이 어느 단계에 쓰이나', 11.5, True, JB_DARK)]])
leg = [(PURPc, PURP_T, 'Ollama · Qwen2.5-7B (LLM 추론)', '(4)LLM 심의 · (5)오인 시뮬레이터 · *오토파일럿 · 내규 변환 · 다국어 재심의'),
       (TEALc, TEAL_T, 'BGE-m3 (임베딩, 선택)', '(2) RAG 근거검색 - 미설치 시 어휘검색으로 자동 폴백'),
       (GREYc, GREY_T, '결정적 엔진 (모델 없음)', '(1) 유형분류 · (3) 룰엔진 · (6) 리포트 · (7,8) 승인·감사 (규칙·집계)')]
ly = cy + I(2.74)
for col, tfill, name, uses in leg:
    box(ix, ly, I(2.85), I(0.37), [[(name, 10, True, col)]], tfill, line=col, align=PP_ALIGN.LEFT, m=0.1)
    tbox(ix + I(2.98), ly, iw - I(2.98), I(0.37), [[('-> ' + uses, 9.7, False, INK)]], anchor=MSO_ANCHOR.MIDDLE)
    ly = ly + I(0.40)

darrow(I(7.65), I(5.5), I(0.34), '조회·기록')
darrow(I(11.35), I(5.5), I(0.34), '연동')

# DB / 외부연동
shp(MSO_SHAPE.CAN, I(6.4), I(5.84), I(1.75), I(1.20),
    [[('SQLite', 10.5, True, WHITE)], [('승인·감사로그', 8.5, False, C('dfe6f0'))], [('내규·배포 로그', 8.5, False, C('dfe6f0'))]],
    JB_DARK, line=None)
shp(MSO_SHAPE.CAN, I(8.3), I(5.84), I(1.75), I(1.20),
    [[('규제 KB', 10.5, True, WHITE)], [('regulations.json', 8, False, C('dfe6f0'))], [('rules.yaml', 8, False, C('dfe6f0'))]],
    C('2a6099'), line=None)
shp(MSO_SHAPE.CLOUD, I(10.2), I(5.70), I(2.68), I(1.50), [], C('fff7e6'), line=AMBER, lw=1.25)
tbox(I(10.2), I(5.86), I(2.68), I(0.26), [[('외부 연동 (어댑터)', 10, True, C('8a6200'))]], align=PP_ALIGN.CENTER)
for i, (nm, fid) in enumerate([('법제처 OpenAPI', 'F14'), ('FCM·SNS·알림톡', 'F15'), ('코어뱅킹 API', 'F16')]):
    tbox(I(10.3), I(6.14) + i * I(0.30), I(2.5), I(0.26),
         [[(nm + '  ', 9, True, C('6b4e00')), (fid, 8.5, True, AMBER)]], align=PP_ALIGN.CENTER)

tbox(I(0.45), SH - I(0.36), I(12.4), I(0.28),
     [[('외부 연동은 어댑터로 분리 - 데모는 목/피드, 운영 시 법제처 OpenAPI·FCM/SNS/알림톡·코어뱅킹 API로 교체 · 전 과정 온프레미스', 9, False, MUTED)]])

out = 'docs/submission/JB준법코파일럿_시스템아키텍처.pptx'
prs.save(out)
print('saved', os.path.getsize(out), 'bytes')
