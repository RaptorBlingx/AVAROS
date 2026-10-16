# Direct-question diagnostic regression corpus

`unseen_en_tr_20261015.json` is an unchanged copy of the original signed-widget evaluation corpus (140 turns: 128 standalone questions and 12 conversational turns).

SHA-256: `9cc99851d1a8186499a57e4a6eaed56ca6b2ba0e769ec18de0bd738144012b7d`.

This is a known regression corpus, not a fresh holdout or training set. Its expected fields describe requests; they do not imply every question currently succeeds. Replay through the signed widget with scoped synthetic Reneryo/MDSP services and assess the actual operation, metric, interval, filters, authorization and delivered answer. A generic clarification is not completion of a supported request.

The focused service tests cover the shared request contracts. Keep new language evaluations separate from this file, and do not add full-question rules to make the corpus pass.
