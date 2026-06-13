"""승인 콘텐츠 → 마케팅 채널 자동 배포 (Last-Mile, F15).

승인(approved)된 콘텐츠를 마케팅 발송 채널로 자동 연계한다. 데모에서는 각 채널
어댑터가 발송을 모의(mock)하고 결과/감사로그를 남긴다. 운영에서는 동일 어댑터
인터페이스를 실제 채널 API로 교체한다:
  push→Firebase FCM · sms→AWS SNS/통신사 · email→SendGrid · sns→Meta/X API ·
  crm→사내 CRM/마케팅 자동화(Braze 등). 미승인 콘텐츠는 배포 불가(휴먼인더루프).
"""
from __future__ import annotations

CHANNELS = {
    "push": "앱 푸시",
    "sms": "SMS",
    "email": "이메일",
    "sns": "SNS",
    "crm": "CRM",
}


def dispatch(channels: list[str], title: str, text: str) -> list[dict]:
    """선택 채널로 배포(모의). 운영 시 각 분기에서 실제 채널 API를 호출."""
    results = []
    for ch in channels:
        if ch not in CHANNELS:
            continue
        # 운영: requests.post(FCM/SNS/...) 등 실제 발송. 데모: 모의 전송 성공.
        results.append({
            "channel": ch,
            "label": CHANNELS[ch],
            "status": "sent",
            "ref": f"mock-{ch}-dispatch",
        })
    return results
