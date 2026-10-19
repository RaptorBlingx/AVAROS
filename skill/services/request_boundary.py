"""Bounded read-only settings/control routing before data interpretation."""

import re

from skill.services.language import normalize_phrase


def read_only_request_kind(utterance: str) -> str:
    """Recognize commands, without treating target/status questions as writes.

    These are unsupported conversational operations, not an authorization
    mechanism. Explicit MDSP evaluation continues through its existing gate.
    """
    text = normalize_phrase(utterance)
    text = re.sub(r"^(?:please |can you |could you |would you |lütfen |lutfen )", "", text)
    settings_target = (
        r"\b(?:settings?|configuration|threshold|target|language|alerts?|alarms?|"
        r"ayar\w*|yapılandır\w*|yapilandir\w*|eşi[ğk]\w*|esi[gk]\w*|"
        r"hedef\w*|dil(?:i|ini)?|uyarı\w*|uyari\w*|alarm\w*)\b"
    )
    settings_command = (
        re.search(r"^(?:set|change|update|adjust|reset|enable|disable|open)\b", text)
        or re.search(
            r"\b(?:değiştir|degistir|ayarla|sıfırla|sifirla|etkinleştir|"
            r"etkinlestir|aç|ac|kapat)(?:ır mısın|ir misin)?$", text,
        )
    )
    if settings_command and re.search(settings_target, text):
        return "settings"
    # Equipment commands require an equipment/process subject; 'start an
    # evaluation', 'show start time' and data questions must keep their routes.
    equipment = (
        r"\b(?:line|hat|hattı|hatti|machine|equipment|motor|pump|compressor|"
        r"boiler|production|makine\w*|ekipman\w*|pompa\w*|kompresör\w*|"
        r"kompresor\w*|kazan\w*|üretim\w*|uretim\w*|meter|sayaç\w*|sayac\w*)\b"
    )
    control_command = (
        re.search(r"^(?:turn on|turn off|switch on|switch off|power on|power off|start|stop|shut down)\b", text)
        or re.search(r"\b(?:aç|ac|kapat|çalıştır|calistir|durdur)(?:ır mısın|ir misin)?$", text)
    )
    if re.search(r"^(?:start|stop) (?:time|date|timestamp|reading|value)\b", text):
        return ""
    return "control" if control_command and re.search(equipment, text) else ""
