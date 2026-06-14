# -*- coding: utf-8 -*-
"""기능별 세션(설명 카드 -> 실제 작동화면) + 하단 자막바 데모 영상 빌드."""
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 30
R = 'C:/Users/nthin/AppData/Local/Temp/reel2'
OUT = 'JB준법코파일럿_시연영상.mp4'

FB = 'C:/Windows/Fonts/malgunbd.ttf'
FR = 'C:/Windows/Fonts/malgun.ttf'


def font(bold, sz):
    return ImageFont.truetype(FB if bold else FR, sz)


JB = (0, 82, 155); JBD = (0, 58, 110); INK = (26, 29, 33); MUT = (150, 163, 180)
WHITE = (255, 255, 255)


def center_text(d, cx, y, text, f, fill, anchor='mm'):
    d.text((cx, y), text, font=f, fill=fill, anchor=anchor)


def title_card(kicker, big, desc, idx=None):
    img = Image.new('RGB', (W, H), JBD)
    d = ImageDraw.Draw(img)
    # 세로 그라데이션
    for y in range(H):
        t = y / H
        c = (int(JB[0]*(1-t)+JBD[0]*t), int(JB[1]*(1-t)+JBD[1]*t), int(JB[2]*(1-t)+JBD[2]*t))
        d.line([(0, y), (W, y)], fill=c)
    # 상단 키커
    center_text(d, W//2, 150, kicker, font(False, 26), (200, 218, 238))
    # 가운데 큰 제목
    center_text(d, W//2, H//2 - 30, big, font(True, 58), WHITE)
    # 액센트 라인
    d.line([(W//2-180, H//2+30), (W//2+180, H//2+30)], fill=(120, 170, 220), width=3)
    # 설명
    if desc:
        center_text(d, W//2, H//2 + 78, desc, font(False, 27), (215, 228, 244))
    # 코너 라벨
    center_text(d, 90, 50, 'JB금융그룹 Fin:AI Challenge', font(True, 18), (210, 224, 240), anchor='lm')
    return img


def _wrap(d, text, f, maxw):
    words = text.split(' ')
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if d.textlength(test, font=f) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def sub_bar(pil_img, text, tag='● 실제 작동 화면'):
    img = pil_img.convert('RGB').copy()
    if img.size != (W, H):
        img = img.resize((W, H))
    d = ImageDraw.Draw(img, 'RGBA')
    f = font(True, 23)
    lines = _wrap(d, text, f, W - 200)[:2]
    line_h = 32
    bar_h = 58 if len(lines) == 1 else 58 + line_h
    y0 = H - bar_h
    d.rectangle([0, y0, W, H], fill=(12, 18, 28, 226))
    d.line([(0, y0), (W, y0)], fill=(0, 130, 220, 255), width=3)
    # 태그(좌측 상단)
    d.text((26, y0 + 17), tag, font=font(True, 16), fill=(120, 200, 255), anchor='lm')
    # 자막(가운데, 1~2줄)
    total = line_h * len(lines)
    sy = y0 + (bar_h - total) // 2 + line_h // 2
    for i, ln in enumerate(lines):
        center_text(d, W // 2, sy + i * line_h, ln, f, WHITE)
    return img


def scenario_diagram():
    """핵심 시나리오 6단계 다이어그램 (MVP 제안서 사용자 시나리오 기반)."""
    img = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    # 제목
    d.text((W // 2, 70), '핵심 시나리오 — 작성부터 배포까지 한 흐름', font=font(True, 30), fill=JBD, anchor='mm')
    d.line([(W // 2 - 300, 100), (W // 2 + 300, 100)], fill=JB, width=3)
    steps = [
        ('1', '작성', '실시간 예방', ['초안 작성 · 상품조건', '자동 주입 → 즉시 룰 검사']),
        ('2', '인지', '오인 시뮬레이터', ['소비자 오해를 작성', '시점에 헤드라인 표시']),
        ('3', '개선', '준법 오토파일럿', ['통과까지 자율 수정', '(법규 + JB 내규)']),
        ('4', '검토·승인', '휴먼인더루프', ['준법감시인 승인', '전 과정 감사로그']),
        ('5', '배포', 'Last-Mile', ['채널 자동 발송', 'AI·사람·시스템 분리기록']),
        ('6', '다국어', '재심의', ['외국어 버전 생성', '직역 오역 검출']),
    ]
    n = len(steps); mx = 36
    gap = 26
    cw = (W - 2 * mx - gap * (n - 1)) // n
    ch = 250
    cy = 150
    for i, (num, name, sub, desc) in enumerate(steps):
        x = mx + i * (cw + gap)
        d.rounded_rectangle([x, cy, x + cw, cy + ch], radius=14, fill=(248, 250, 253), outline=JB, width=2)
        d.rectangle([x, cy, x + cw, cy + 8], fill=JB)
        # 번호 배지
        bx, by = x + cw // 2, cy + 52
        d.ellipse([bx - 26, by - 26, bx + 26, by + 26], fill=JB)
        d.text((bx, by), num, font=font(True, 28), fill=(255, 255, 255), anchor='mm')
        d.text((bx, cy + 110), name, font=font(True, 25), fill=INK, anchor='mm')
        d.text((bx, cy + 142), sub, font=font(True, 16), fill=JB, anchor='mm')
        for j, line in enumerate(desc):
            d.text((bx, cy + 178 + j * 26), line, font=font(False, 15), fill=MUT, anchor='mm')
        if i < n - 1:
            ax = x + cw + gap // 2
            d.text((ax, cy + ch // 2), '▶', font=font(True, 20), fill=(150, 163, 180), anchor='mm')
    # 상시 규제 자동 추적 배너
    by0 = cy + ch + 40
    d.rounded_rectangle([mx, by0, W - mx, by0 + 70], radius=12, fill=(255, 247, 230), outline=(199, 138, 6), width=2)
    d.text((mx + 24, by0 + 35), '[ 상시 ]  규제 자동 추적', font=font(True, 22), fill=(138, 98, 0), anchor='lm')
    d.text((mx + 280, by0 + 35), '규제 변경 감지 → 영향분석 → 룰 제안 → 준법감시인 승인으로 룰셋 최신화 (운영: 법제처 OpenAPI)',
           font=font(False, 18), fill=INK, anchor='lm')
    return img


def fit_canvas(path, crop=None, bg=(244, 246, 248)):
    im = Image.open(path).convert('RGB')
    if crop:
        im = im.crop(crop)
    cw, ch = im.size
    scale = min(W / cw, (H - 76) / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    im = im.resize((nw, nh))
    canvas = Image.new('RGB', (W, H), bg)
    canvas.paste(im, ((W - nw)//2, max(0, ((H - 76) - nh)//2)))
    return canvas


def fit_top(pil, bg=(255, 255, 255)):
    """이미지를 자막바 위 영역(1280x644)에 통째로 맞춰 배치 (다이어그램 안 가림).
    투명 PNG는 흰색 배경에 합성한다(검정 합성 방지)."""
    if pil.mode in ('RGBA', 'LA', 'P'):
        pil = pil.convert('RGBA')
        bbox = pil.getbbox()        # 투명 여백 제거 → 내용 기준 가운데 정렬
        if bbox:
            pil = pil.crop(bbox)
        base = Image.new('RGB', pil.size, bg)
        base.paste(pil, mask=pil.split()[-1])
        im = base
    else:
        im = pil.convert('RGB')
    cw, ch = im.size
    scale = min(W / cw, (H - 76) / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    im = im.resize((nw, nh))
    canvas = Image.new('RGB', (W, H), bg)
    canvas.paste(im, ((W - nw) // 2, (H - 76 - nh) // 2))
    return canvas


def pil_to_bgr(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# ===== 스토리보드 =====
def D(name):
    """1280x720 뷰포트 캡처를 그대로 사용 (풀프레임)."""
    return Image.open(f'{R}/{name}.png').convert('RGB')


clips = []  # (bgr_image, seconds)


def add(img, sec):
    clips.append((pil_to_bgr(img), sec))


# 인트로
add(title_card('서비스 시연', 'JB 준법 코파일럿', '소비자 오인 방지 중심 준법자문 AI Agent'), 4.5)

# ===== 서비스 소개: AI Agent 구조 (아키텍처) =====
add(title_card('서비스 소개', 'AI Agent 구조',
               '판단·행동·검증을 스스로 수행하는 온프레미스 AI Agent'), 4.5)
add(sub_bar(fit_top(Image.open(f'{R}/v_arch.png')),
            '사용자의 입력이 프론트엔드와 백엔드를 거쳐 AI Agent로 처리되고 그 결과가 DB와 외부 연동으로 이어지며, 모든 추론은 온프레미스의 Qwen2.5-7B로 수행되어 데이터가 내부망 밖으로 나가지 않습니다.',
            tag='● 시스템 아키텍처'), 8.0)

# ===== 핵심 시나리오 6단계 =====
add(title_card('핵심 시나리오', '작성부터 배포까지 한 흐름',
               '작성·인지·개선·검토·배포·다국어 6단계로 이어지는 준법 워크플로'), 4.5)
add(sub_bar(scenario_diagram(),
            '담당자가 초안을 쓰는 순간부터 심의·개선·승인·배포·다국어까지 한 흐름으로 이어지고, 규제 변경은 상시 추적되어 룰셋이 최신으로 유지됩니다.',
            tag='● 핵심 시나리오'), 8.5)

S = [
    ('1단계 · 작성', '작성 시점 실시간 심의',
     '작성하는 순간 룰엔진이 즉시 검사하고 LLM·시뮬레이터가 보강합니다',
     D('v_ws'),
     '광고 초안을 쓰다가 잠시 멈추면 룰엔진이 곧바로 검사해, 위험한 표현에 밑줄을 긋고 준법 점수를 실시간으로 보여 줍니다.'),
    ('2단계 · 인지', '소비자 오인 시뮬레이터',
     '취약 소비자가 광고를 어떻게 오해하는지 작성 시점에 재현합니다',
     D('v_sim'),
     '고령자·금융초보·외국인 소비자가 이 광고를 어떻게 읽고 오해하는지 1인칭으로 재현하고, 오해를 부른 문구와 관련 규제 조항을 함께 짚어 줍니다.'),
    ('2단계 · 비교', '안전 초안은 오해가 줄어듭니다',
     '같은 시뮬레이터로 안전(준법) 초안을 보면 등급이 통과로 바뀝니다',
     D('v_safe'),
     '같은 시뮬레이터에 안전하게 고친 초안을 넣으면 룰 위반이 사라져 준법 등급이 통과로 바뀌고, 소비자 오해도 위험에서 주의 수준으로 완화됩니다.'),
    ('3단계 · 개선', '준법 오토파일럿',
     '위반 초안을 준법 통과 등급까지 스스로 고쳐 씁니다',
     D('v_autopilot'),
     '위반이 있는 초안을 두면 오토파일럿이 심의·고쳐쓰기·재심의를 스스로 반복해 50점에서 94점 통과까지 끌어올리고, 끝내 통과하지 못하면 사람에게 넘깁니다.'),
    ('4단계 · 검토·승인', '준법관리자 검토·승인',
     'AI 1차심의를 근거로 사람이 승인, 모든 이력은 감사로그로 남습니다',
     D('s_approve'),
     'AI의 1차 심의 결과를 근거로 준법관리자가 원문을 직접 검토했는지 확인한 뒤 승인하며, 모든 판단의 최종 책임은 사람에게 있습니다.'),
    ('5단계 · 배포', '마케팅 배포 Last-Mile',
     '승인된 콘텐츠만 채널로 자동 발송됩니다',
     D('s_distribute'),
     '승인된 콘텐츠만 푸시·SMS·이메일 같은 마케팅 채널로 자동 발송되고, AI의 개선과 사람의 승인, 시스템의 배포가 각각 분리되어 감사로그에 기록됩니다.'),
    ('6단계 · 다국어', '다국어 생성·재심의',
     '외국어 버전을 만들고 직역 오역까지 다시 심의합니다',
     D('s_multilingual'),
     '승인본의 외국어 버전을 자동으로 만들고 다시 심의해, 직역 과정에서 생기는 보장성 오역이나 고지 누락을 잡아냅니다.'),
]

for kicker, big, desc, demo_img, sub in S:
    add(title_card(kicker, big, desc), 4.0)
    add(sub_bar(demo_img, sub), 6.5)

# ===== 마무리 =====
add(title_card('Thank you', '감사합니다',
               'JB 준법 코파일럿 · JB금융그룹 Fin:AI Challenge 지정주제2'), 5.0)

# ===== 인코딩 (크로스페이드) =====
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
vw = cv2.VideoWriter(OUT, fourcc, FPS, (W, H))
XF = int(0.35 * FPS)


def hold(img, sec):
    for _ in range(int(sec * FPS)):
        vw.write(img)


def fade(a, b):
    for i in range(XF):
        al = i / XF
        vw.write(cv2.addWeighted(a, 1 - al, b, al, 0))


for img, sec in clips:
    hold(img, sec)          # 하드컷 (크로스페이드 제거 — 겹침 방지)
vw.release()
print('saved', OUT, os.path.getsize(OUT), 'bytes', len(clips), 'clips')
