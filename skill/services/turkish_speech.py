"""Turkish speech rendering of presentation text; never used for source data."""

from __future__ import annotations

import re
from datetime import date

_ONES = ('sıfır', 'bir', 'iki', 'üç', 'dört', 'beş', 'altı', 'yedi', 'sekiz', 'dokuz')
_TENS = ('', 'on', 'yirmi', 'otuz', 'kırk', 'elli', 'altmış', 'yetmiş', 'seksen', 'doksan')
_MONTHS = ('Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
           'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık')


def cardinal(value: int) -> str:
    """Spell a Turkish integer, retaining every digit even outside our scale."""
    if value < 0:
        return 'eksi ' + cardinal(-value)
    if value < 10:
        return _ONES[value]
    if value < 100:
        return _TENS[value // 10] + (' ' + _ONES[value % 10] if value % 10 else '')
    if value < 1000:
        head = (cardinal(value // 100) + ' ' if value >= 200 else '') + 'yüz'
        return head + (' ' + cardinal(value % 100) if value % 100 else '')
    for scale, name in ((10**12, 'trilyon'), (10**9, 'milyar'), (10**6, 'milyon'), (1000, 'bin')):
        if value >= scale and value < scale * 1000:
            head = ('' if value // scale == 1 and scale == 1000 else cardinal(value // scale) + ' ') + name
            return head + (' ' + cardinal(value % scale) if value % scale else '')
    return ' '.join(_ONES[int(digit)] for digit in str(value))


def spoken_number(value: str) -> str:
    """Read locale-formatted decimals, preserving leading fractional zeros."""
    value = value.replace('.', '')
    sign = 'eksi ' if value.startswith('-') else 'artı ' if value.startswith('+') else ''
    integer, _, fraction = value.lstrip('+-').partition(',')
    result = sign + cardinal(int(integer))
    if fraction:
        digits = (' '.join(_ONES[int(d)] for d in fraction) if fraction.startswith('0')
                  else cardinal(int(fraction)))
        result += ' virgül ' + digits
    return result


def _date(match: re.Match) -> str:
    day, month, year = (int(match['day']), int(match['month']), int(match['year']))
    try:
        date(year, month, day)
    except ValueError:
        return match[0]
    return f'{cardinal(day)} {_MONTHS[month - 1]} {cardinal(year)}'


def _clock(match: re.Match) -> str:
    hour, minute = int(match[1]), int(match[2])
    if hour == minute == 0:
        return 'gece yarısı'
    return 'saat ' + cardinal(hour) + (' ' + cardinal(minute) if minute else '')


def render_turkish_speech(text: str) -> str:
    """Expand dates, explicit clocks, quantities and abbreviations for TTS.

    A colon alone does not identify a clock: bare times/durations and source
    identifiers are protected. Only a dated time or an explicit 'saat' is read
    as a clock. Reapplying this renderer leaves its output unchanged.
    """
    parts = re.split(r'(\[\[.*?\]\]|https?://\S+)', text)
    return ''.join(_render_fragment(_narrate_fragment(part)) if index % 2 == 0 else part
                   for index, part in enumerate(parts))


def weather_delay_name(title: str) -> str | None:
    """Recognize only exact source-attributed weather delay titles."""
    from skill.services.response_localization import source_metric_label

    suffix = " - Open Weather kaynağında gecikme algılandı"
    if not title.endswith(suffix):
        return None
    name = title[:-len(suffix)]
    if name not in ("Heating degree days", "Cooling degree days", "Temperature", "Humidity", "Rain"):
        return None
    return source_metric_label(name + " - Open Weather", "tr-TR")


def weather_delay_speech(names: list[str]) -> str:
    """State a shared delay without implying equal lag or a common cause.

    MDSP freshness findings concern one metric resource. "Open Weather" is
    part of the metric's name, not the lagging resource's provenance: a
    metric can have an imported resource that lags while its OpenWeather
    integration is current. Speech therefore names only the metric.
    """
    if set(names) == {"ısıtma derece gün değeri", "soğutma derece gün değeri"} and len(names) == 2:
        subject = "ısıtma ve soğutma derece gün"
    else:
        subjects = [name.removesuffix(" değeri") for name in names]
        subject = ", ".join(subjects[:-1]) + " ve " + subjects[-1] if len(subjects) > 1 else subjects[0]
    return f"{subject} {'kaynaklarında' if len(names) > 1 else 'kaynağında'} gecikme var"


def _weather_measurements(text: str) -> str:
    """Share attribution only for adjacent, explicitly attributed readings."""
    from skill.services.response_localization import source_metric_label

    reading = r"(?<![\w-])(Temperature|Humidity|Rain) - Open Weather: ((?:%\s*)?[+-]?\d+(?:\.\d{3})*(?:,\d+)?(?:\s*(?:°C|mm|%))?)\."

    def narrate(match: re.Match) -> str:
        rows = re.findall(reading, match[0])
        clauses = [f"{source_metric_label(name + ' - Open Weather', 'tr-TR')} {value}" for name, value in rows]
        body = ", ".join(clauses[:-1]) + " ve " + clauses[-1] if len(clauses) > 1 else clauses[0]
        return "OpenWeather verilerine göre " + body + "." + (" " if match[0][-1:].isspace() else "")

    return re.sub(r"(?:" + reading + r"(?:\s+|$))+", narrate, text)


def _narrate_fragment(text: str) -> str:
    """Smooth exact AVAROS presentation templates; keep unknown prose intact."""
    # No global punctuation replacement: decimal points, identifiers, URLs,
    # quoted source prose and technical qualifiers must retain their meaning.
    text = _weather_measurements(text)
    text = re.sub(
        r"(?<![\w-])(?:Heating degree days|Cooling degree days|Temperature|Humidity|Rain) - Open Weather kaynağında gecikme algılandı(?!\w)",
        lambda match: weather_delay_speech([weather_delay_name(match[0])]), text,
    )
    replacements = {
        # A finding names one lagging source, not the metric's data as a whole.
        "kaynağında gecikme algılandı": "kaynağında gecikme var",
        "Kayıt zamanı: ": "Son kayıt ",
        "Reneryo dönem tüketimi; veri kapsamı eksik olabilir.": "Bu, Reneryo'daki dönem tüketimi. Veri kapsamı eksik olabilir.",
    }
    for original, spoken in replacements.items():
        text = text.replace(original, spoken)
    # Both counter-reading templates (metric and factory routes) share one reading.
    text = re.sub(r"Bu birikimli sayaç değeridir[;,] dönem tüketimi veya üretimi değildir\.",
                  "Bu, birikimli sayaç değeri; dönem tüketimi ya da üretimi değil.", text)
    text = re.sub(r"Bu (gelişmiş|doğrusal) regresyon modeli (günlük|haftalık|aylık) dönemlidir ve (birincil değil|birincil)\.",
                  lambda m: f"{m[2].capitalize()} dönemli bu {m[1]} regresyon modeli " + ("birincil değil." if m[3] == "birincil değil" else "birincil olarak işaretli."), text)
    text = re.sub(r"Açıklayıcı değişkenler: (.+?)\. Bağlı dilimler: (.+?)\. Eğitim dönemi ",
                  r"Modelde \1 kullanılıyor. Bağlı dilimler \2. Eğitim dönemi ", text)
    text = re.sub(r"Eğitim dönemi (\d{4}-\d{2}-\d{2}) – (\d{4}-\d{2}-\d{2}); ", r"Eğitim dönemi \1 ile \2. ", text)
    return text


def _render_fragment(text: str) -> str:
    """Render ordinary presentation text outside URLs and raw phonemes."""
    def dated_time(match: re.Match) -> str:
        rendered = _date(match)
        if match['clock'] and rendered != match[0]:
            clock = re.match(r'(\d{2}):(\d{2})', match['clock'])
            return rendered + ' ' + _clock(clock)
        return rendered

    text = re.sub(r'(?<![\w/-])(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})(?: (?P<clock>(?:[01]\d|2[0-3]):[0-5]\d))?(?![\d:])', dated_time, text)
    text = re.sub(r'(?<![\w/-])(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(?![\dT])', _date, text)
    text = re.sub(r'(?<![\w-])(\d{4})-(0[1-9]|1[0-2])(?![\d-])', lambda m: f'{_MONTHS[int(m[2]) - 1]} {cardinal(int(m[1]))}', text)
    text = re.sub(r'\bsaat ([01]?\d|2[0-3]):([0-5]\d)(?![:\d])', _clock, text)

    def zone(match: re.Match) -> str:
        name = 'İstanbul saati' if match[1] == 'Europe/Istanbul' else match[1].replace('/', ' ').replace('_', ' ') + ' saat dilimi'
        offset = ('artı ' if match[2] == '+' else 'eksi ') + cardinal(int(match[3])) + ' saat'
        if int(match[4]):
            offset += ' ' + cardinal(int(match[4])) + ' dakika'
        return f'{name}, UTC {offset}'

    text = re.sub(r'\(([A-Za-z0-9_+/-]+), UTC([+-])(\d{2}):(\d{2})\)', zone, text)
    units = {
        'kWh/unit': 'birim başına kilovatsaat', 'kWh': 'kilovatsaat',
        'MWh': 'megavatsaat', 'kW': 'kilovat', 'MW': 'megavat',
        '°C': 'derece', 'm³': 'metreküp', 'm3': 'metreküp',
        'kg': 'kilogram', 'Hz': 'hertz', 'mm': 'milimetre',
    }
    for unit, spoken in units.items():
        # Written case endings belong to the unit, not the decimal number.
        for ending, suffix in (("den", 'den'), ("dan", 'den'), ("ye", 'ye'), ("ya", 'ye')) if unit == '°C' else ():
            text = re.sub(rf"(?<=\d)\s*{re.escape(unit)}['’]{ending}\b", ' ' + spoken + suffix, text)
        text = re.sub(rf'(?<=\d)\s*{re.escape(unit)}(?![\w/])', ' ' + spoken, text)
    text = re.sub(r'\bderece (artış|düşüş)\b', r'derecelik bir \1', text)
    number = r'[+-]?\d+(?:\.\d{3})*(?:,\d+)?'
    text = re.sub(rf'%\s*({number})', r'yüzde \1', text)
    text = re.sub(rf'({number})\s*%', r'yüzde \1', text)
    # Individual Turkish readings: system initials MDSP, factory OEE/KPI,
    # mathematical R-squared and the UTC time standard retain their readings.
    # RMSE is clearer as the established Turkish statistical term.
    abbreviations = {'MDSP': 'em de se pe', 'OEE': 'o e e', 'KPI': 'ka pe i',
                     'UTC': 'evrensel eşgüdümlü zaman', 'R²': 'er kare', 'RMSE': 'kök ortalama kare hatası'}
    for label, spoken in abbreviations.items():
        text = re.sub(rf'(?<!\w){re.escape(label)}(?!\w)', spoken, text)
    # Preserve URLs, IDs, raw phonemes and colon-form durations verbatim.
    protected = r'(\[\[.*?\]\]|https?://\S+|\b[\w]+(?:[-/:][\w]+)+\b)'
    parts = re.split(protected, text)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(rf'(?<![\w.,]){number}(?!\w|[.,]\d)', lambda m: spoken_number(m[0]), parts[index])
    return ''.join(parts)
