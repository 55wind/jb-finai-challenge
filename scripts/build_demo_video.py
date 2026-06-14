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


def sub_bar(pil_img, text, tag='● 실제 작동 화면'):
    img = pil_img.convert('RGB').copy()
    if img.size != (W, H):
        img = img.resize((W, H))
    d = ImageDraw.Draw(img, 'RGBA')
    bar_h = 76
    y0 = H - bar_h
    d.rectangle([0, y0, W, H], fill=(12, 18, 28, 220))
    d.line([(0, y0), (W, y0)], fill=(0, 130, 220, 255), width=3)
    # 태그(좌측)
    d.text((26, y0 + bar_h//2), tag, font=font(True, 17), fill=(120, 200, 255), anchor='lm')
    # 자막(가운데)
    center_text(d, W//2, y0 + bar_h//2, text, font(True, 24), WHITE)
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


def fit_top(pil, bg=(247, 249, 251)):
    """이미지를 자막바 위 영역(1280x644)에 통째로 맞춰 배치 (다이어그램 안 가림)."""
    im = pil.convert('RGB'); cw, ch = im.size
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
add(title_card('기능 시연', 'JB 준법 코파일럿', '소비자 오인 방지 중심 준법자문 AI Agent'), 3.0)

S = [
    ('기능 ①', '작성 시점 실시간 심의',
     '작성하는 순간 룰엔진이 즉시 검사하고 LLM·시뮬레이터가 보강합니다',
     D('v_ws'),
     '타이핑을 멈추면 즉시 룰 검사 → 위험 문구 자동 밑줄 · 준법점수 표시'),
    ('기능 ②', '소비자 오인 시뮬레이터',
     '취약 소비자가 광고를 어떻게 오해하는지 작성 시점에 재현합니다',
     D('v_sim'),
     '고령자·금융초보·외국인이 1인칭으로 오해 → 유발 문구 + 규제 조항 연결'),
    ('비교', '안전 초안은 오해가 줄어듭니다',
     '같은 시뮬레이터로 안전(준법) 초안을 보면 등급이 통과로 바뀝니다',
     D('v_safe'),
     '안전(준법) 초안 — 준법 통과(94) · 위반 0 · 페르소나 오해 "위험→주의"로 완화'),
    ('기능 ③', '준법 오토파일럿',
     '위반 초안을 준법 통과 등급까지 스스로 고쳐 씁니다',
     D('v_autopilot'),
     '심의→고쳐쓰기→재심의 반복 · 50→94 통과 (미수렴 시 사람 에스컬레이션)'),
    ('기능 ④', '준법관리자 검토·승인',
     'AI 1차심의를 근거로 사람이 승인, 모든 이력은 감사로그로 남습니다',
     D('s_approve'),
     '원문 직접 검토 확인 후 승인 — 최종 판단·책임은 준법감시인'),
    ('기능 ⑤', '마케팅 배포 Last-Mile',
     '승인된 콘텐츠만 채널로 자동 발송됩니다',
     D('s_distribute'),
     '승인본을 채널로 자동 발송 · AI 개선→사람 승인→시스템 배포 분리 기록'),
    ('기능 ⑥', '다국어 생성·재심의',
     '외국어 버전을 만들고 직역 오역까지 다시 심의합니다',
     D('s_multilingual'),
     '외국어 버전 생성·재심의로 직역 보장성 오역·고지 누락 검출'),
]

for kicker, big, desc, demo_img, sub in S:
    add(title_card(kicker, big, desc), 2.6)
    add(sub_bar(demo_img, sub), 4.2)

# ===== 마무리: 아키텍처 → 태그라인 → 감사합니다 =====
add(title_card('아키텍처', '온프레미스 · 오픈모델 구조',
               '데이터를 내부망 밖으로 내보내지 않는 온프레미스 AI Agent'), 2.8)
add(sub_bar(fit_top(D('v_arch')),
            '사용자→프론트엔드→백엔드(AI Agent)→DB/외부연동 · Qwen2.5-7B 온프레미스 추론 · 데이터 외부 유출 0',
            tag='● 시스템 아키텍처'), 5.5)
add(title_card('JB 준법 코파일럿', '심의는 AI가, 판단은 사람이',
               '온프레미스 · 오픈모델(Qwen2.5-7B) · 전 과정 휴먼인더루프'), 3.0)
add(title_card('Thank you', '감사합니다',
               'JB 준법 코파일럿 · JB금융그룹 Fin:AI Challenge 지정주제2'), 3.8)

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
