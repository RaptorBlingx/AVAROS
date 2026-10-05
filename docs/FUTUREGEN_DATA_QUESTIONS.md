# Future Gen: questions to ask AVAROS

Verified against Reneryo on **5 October 2026**. The answer improvements described here are on the local `feat/futuregen-historical-answers` branch; they have **not been deployed**. API checks ran as isolated read-only diagnostics, without changing the running assistant.

## Available data

| Data | What can be answered | Current coverage |
| --- | --- | --- |
| Factory electricity | Reneryo meter consumption for a requested period; monthly metric history; latest cumulative reading and its timestamp | Monthly history from 2024; latest available monthly period June 2026 |
| Factory production | Reneryo monthly production values; historical series; latest cumulative reading and its timestamp | Monthly history from 2024; latest available monthly period July 2026 |
| Weather | Temperature, humidity, rainfall, heating and cooling degree-day metrics and trends | Historical daily records and current OpenWeather observations; ask for a specific metric |
| Decision Support | Active findings, severity filtering, evidence, affected entities and grounded next-review guidance | Separate MDSP findings flows already supported by the MVP |

Old observations remain usable. An empty requested window triggers an explicit explanation and dated historical evidence. It never turns an old value into today's value, and missing observations never mean zero consumption.

## Electricity: English / Turkish

| English | Turkish |
| --- | --- |
| What is our electricity consumption? | Elektrik tüketimimiz ne kadar? |
| Show latest electricity consumption. | Son elektrik tüketimini göster. |
| How much energy did we use today? | Bugün ne kadar enerji tükettik? |
| Show electricity consumption last month. | Geçen ay elektrik tüketimini göster. |
| How much electricity was consumed in June 2026? | Haziran 2026 elektrik tüketimi ne kadar? |
| Show electricity consumption from May to June 2026. | Mayıs ile Haziran 2026 elektrik tüketimini göster. |
| Show energy use in 2024. | 2024 enerji tüketimini göster. |
| Show electricity history. | Elektrik geçmişini göster. |
| Show all electricity history. | Tüm elektrik geçmişini göster. |
| Show electricity data from May to June 2026. | Mayıs ile Haziran 2026 elektrik verisini göster. |
| What is the latest electricity reading? | Son elektrik değerini göster. |
| When was electricity last updated? | Elektrik verisi ne zaman kaydedildi? |
| Show electricity trend from May to June 2026. | Mayıs ile Haziran 2026 elektrik eğilimini göster. |
| Show electricity trend today. | Bugün elektrik eğilimini göster. |

Unspecified consumption questions use the **latest available monthly period**. A dated consumption answer uses Reneryo's meter calculation. History and trends use Reneryo's metric aggregates; they are labelled separately. A counter-reading answer explicitly identifies a cumulative value. The APIs expose unit groups; the assistant does not invent a more specific unit symbol.

## Production: English / Turkish

| English | Turkish |
| --- | --- |
| How much production do we have? | Ne kadar ürettik? |
| Show latest production. | Son üretim miktarını göster. |
| What did we produce in July 2026? | Temmuz 2026 üretim miktarı ne kadar? |
| Show factory output last month. | Geçen ay üretimi göster. |
| How much was produced today? | Bugün üretimimiz ne kadar? |
| Show production history. | Üretim geçmişini göster. |
| Show all production history. | Tüm üretim geçmişini göster. |
| Show available production data. | Mevcut üretim verisini göster. |
| Show production history in 2024. | 2024 üretim geçmişini göster. |
| Show production data from May to July 2026. | Mayıs ile Temmuz 2026 üretim verisini göster. |
| Show cumulative production reading. | Birikimli üretim değerini göster. |
| How fresh is production data? | Üretim verisi ne kadar güncel? |
| Show production trend from May to July 2026. | Mayıs ile Temmuz 2026 üretim eğilimini göster. |

An unspecified production amount returns the latest available monthly value. A multi-month request shows the domain-provided monthly values, rather than inventing a total. There is no verified Reneryo multi-month production-total contract in this answer path.

## Follow-ups and dates

After “Show electricity consumption”, try **“And June?”**. After a dated production answer, try **“When was the last reading recorded?”**, **“Show history”** or **“Show its trend”**. Turkish equivalents include **“Peki Haziran?”**, **“Son veri ne zaman kaydedildi?”**, **“Geçmişini göster”** and **“Eğilimini göster”**. A month-only follow-up inherits the year of the historical answer. Switching to production explicitly switches the metric.

Named months, month ranges, calendar years and explicit date ranges are accepted. Examples: **“Electricity consumption from 2026-05-01 to 2026-06-30”** / **“2026-05-01 ile 2026-06-30 elektrik tüketimini göster”**. Dates in evidence identify the API-returned bucket or reading time. Monthly factory observations do not prove daily or hourly coverage.

Default history displays the most recent 12 monthly buckets and states how many are available. **“All history” / “Tüm geçmiş”** requests the full paginated monthly history. The spoken answer previews a few values; the evidence panel retains the returned series. A trend is a first-to-last observed-period comparison, not a forecast or a claim about every intervening day.

## Other useful existing flows

- **“Show temperature trend today” / “Bugün sıcaklık eğilimini göster”**; ask similarly for humidity, rainfall, heating or cooling degree days.
- **“List active findings” / “Etkin bulguları listele”**, then **“Explain the first one” / “İlkini açıkla”** and **“Show its evidence” / “Kanıtını göster”**.
- **“Show Future Gen meters for June 2026” / “Haziran 2026 için Future Gen sayaçlarını göster”**.

Ask electricity and production separately. If multiple counter metrics match, AVAROS asks for a named selection. Questions about cost, savings, forecasts, per-unit efficiency, OEE or root causes need their own verified data and calculation contracts; these historical answers do not manufacture them. A genuine API or access failure remains an availability error, not an empty-data fallback. Voice uses the same answer path; speech recognition and pronunciation still need a separate rehearsal after deployment.
