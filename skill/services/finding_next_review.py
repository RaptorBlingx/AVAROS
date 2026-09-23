"""Narrate MDSP's structured next-review assessment without creating advice."""

from skill.domain.reneryo_models import MdspFinding
from skill.services.language import is_turkish


def next_review_headline(finding: MdspFinding, action: str, language: str) -> str:
    turkish = is_turkish(language)
    if finding.retired_at:
        return (
            "Bu tarihsel bulgu kural kapsamı düzeltildiği için kaldırıldı; geçerli bir sonraki inceleme önerisi yok."
            if turkish else
            "This historical finding was retired after a rule-scope correction; it has no current next-review suggestion."
        )
    if finding.status != "ACTIVE":
        return (
            "Bu bulgu artık aktif değil. Son inceleme önerisi güncel bir eylem olarak sunulamaz."
            if turkish else
            "This finding is no longer active. Its last review suggestion is not a current action."
        )
    review = finding.next_review
    if action == "finding.owner":
        return (
            "Bu bulgu için Reneryo'da onaylı bir sorumlu ataması sağlanmadı."
            if turkish else
            "No approved Reneryo owner assignment is available for this finding."
        )
    if action == "finding.can_act":
        if review and review.review_link:
            return (
                "İnceleme sayfasını gösterebilirim; bu bulgu için kayıt veya model değişikliği yapamam."
                if turkish else
                "I can point you to the review page; I cannot change records or models for this finding."
            )
        return (
            "Bu bulgu için bir işlem gerçekleştiremiyorum; desteklenen bir inceleme bağlantısı da yok."
            if turkish else
            "I cannot take action on this finding, and no supported review link is available."
        )
    if review is None:
        if finding.next_review_abstention:
            return finding.next_review_abstention.for_language(language)
        return (
            "Bu bulgu için desteklenen bir sonraki inceleme önerisi mevcut değil."
            if turkish else "No supported next review is available for this finding."
        )
    if action == "finding.next_review_why":
        label = "Geçici politika" if turkish else "Provisional policy"
        if review.policy_status == "APPROVED":
            label = "Onaylı politika" if turkish else "Approved policy"
        fields = ", ".join(review.evidence_keys)
        if turkish:
            return (
                f"{review.rationale.for_language(language)} {label}; dayanak: "
                f"{finding.rule_id} v{finding.rule_version}, kanıt alanları: {fields}."
            )
        return (
            f"{review.rationale.for_language(language)} {label}; basis: "
            f"{finding.rule_id} v{finding.rule_version}, evidence fields: {fields}."
        )
    status = "Geçici inceleme önerisi" if turkish else "Provisional next review"
    if review.policy_status == "APPROVED":
        status = "Onaylı inceleme önerisi" if turkish else "Approved next review"
    return f"{status}: {review.instruction.for_language(language)}"
