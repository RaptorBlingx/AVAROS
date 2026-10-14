"""Localized AVAROS-owned recovery text; source names and payloads stay raw."""

from skill.services.language import is_turkish


_TURKISH_SYSTEM_TEXT = {
    "This meter only exposes a cumulative total. Ask for total energy without a period.": "Bu sayaç yalnızca birikimli toplam sunuyor. Dönem belirtmeden toplam enerjiyi sorun.",
    "Which manufacturing metric do you mean?": "Hangi üretim metriğini kastediyorsunuz?",
    "Which manufacturing metric should I explain?": "Hangi üretim metriğini açıklamamı istiyorsunuz?",
    "Which asset should I use?": "Hangi ekipmanı kullanmamı istiyorsunuz?",
    "Please name at least two assets, or say all lines.": "En az iki ekipman adı belirtin veya tüm hatlar deyin.",
    "No mapped summary data was available for that scope.": "Bu kapsam için yapılandırılmış özet verisi bulunamadı.",
    "AVAROS is still initializing. Please try again.": "AVAROS henüz başlatılıyor. Lütfen tekrar deneyin.",
    "Sorry, I encountered an error. Please try again.": "İsteği işlerken bir hata oluştu. Lütfen tekrar deneyin.",
    "The data platform did not respond in time. Please check the platform connection and try again.": "Veri platformu zamanında yanıt vermedi. Platform bağlantısını kontrol edip tekrar deneyin.",
    "Reneryo data is temporarily unavailable.": "Reneryo verilerine şu anda erişilemiyor.",
    "The Reneryo data source is not configured.": "Reneryo veri kaynağı yapılandırılmamış.",
    "Decision-support findings are not configured in AVAROS.": "AVAROS'ta karar destek bulguları yapılandırılmamış.",
    "Decision-support findings are temporarily unavailable.": "Karar destek bulgularına şu anda erişilemiyor.",
    "That decision-support finding is no longer available.": "Bu karar destek bulgusu artık mevcut değil.",
    "I couldn't find data for that period.": "Bu dönem için veri bulunamadı.",
    "The configured aggregation for this metric is invalid.": "Bu metrik için yapılandırılmış toplama yöntemi geçersiz.",
    "I'm having trouble connecting to the data source. Please try again.": "Veri kaynağına bağlanılamıyor. Lütfen tekrar deneyin.",
    "I encountered an error processing your request.": "İsteği işlerken bir hata oluştu.",
}


def localized_system_text(text: str, language: str | None) -> str:
    """Translate only exact owned templates, never arbitrary source strings."""
    return _TURKISH_SYSTEM_TEXT.get(text, text) if is_turkish(language) else text


def localized_error_message(error, language: str | None) -> str:
    """Use typed failure semantics when no exact Turkish template is available."""
    text = error.user_message
    translated = localized_system_text(text, language)
    if not is_turkish(language) or translated != text:
        return translated
    code = error.code
    if code == "METRIC_NOT_SUPPORTED":
        return "İstenen metrik için şu anda veri mevcut değil."
    if code == "ASSET_NOT_FOUND":
        return f"{error.asset_id} adlı ekipman bulunamadı."
    if code == "VALIDATION_ERROR":
        return "İstenen kapsam veya dönem anlaşılamadı. Lütfen isteğinizi yeniden belirtin."
    if "NOT_CONFIGURED" in code or code == "CONFIG_ERROR":
        return "İstenen veri veya işlem yapılandırılmamış. Lütfen sistem yöneticinizle görüşün."
    if code == "GENERIC_REST_NO_DATA":
        return "İstenen dönem için kullanılabilir veri bulunamadı."
    if code == "GENERIC_REST_PERIOD_UNSUPPORTED":
        return "Bu veri kaynağı istenen dönem için değer sunmuyor; en güncel değeri dönem verisi olarak kullanmadım."
    if code.startswith(("GENERIC_REST_", "RENERYO_", "MDSP_")) or code == "ADAPTER_ERROR":
        return "Veri kaynağından kullanılabilir bir yanıt alınamadı. Lütfen bağlantıyı ve yapılandırmayı kontrol edin."
    return "İsteği işlerken bir hata oluştu. Lütfen tekrar deneyin."
