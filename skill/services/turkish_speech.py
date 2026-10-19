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
    return ''.join(_render_fragment(part) if index % 2 == 0 else part
                   for index, part in enumerate(parts))


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
    abbreviations = {'MDSP': 'em de se pe', 'OEE': 'o e e', 'KPI': 'ka pe i',
                     'UTC': 'evrensel eşgüdümlü zaman', 'R²': 'er kare', 'RMSE': 'er em se e'}
    for label, spoken in abbreviations.items():
        text = re.sub(rf'(?<!\w){re.escape(label)}(?!\w)', spoken, text)
    # Preserve URLs, IDs, raw phonemes and colon-form durations verbatim.
    protected = r'(\[\[.*?\]\]|https?://\S+|\b[\w]+(?:[-/:][\w]+)+\b)'
    parts = re.split(protected, text)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(rf'(?<![\w.,]){number}(?!\w|[.,]\d)', lambda m: spoken_number(m[0]), parts[index])
    return ''.join(parts)
