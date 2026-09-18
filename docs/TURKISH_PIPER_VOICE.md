# Turkish Piper voice

AVAROS uses the existing in-process Piper TTS path for both supported locales:

- `en-US`: `en_US-lessac-medium`
- `tr-TR`: `tr_TR-dfki-medium`

The Turkish model is pinned to piper-voices revision
`c10ece1aade47bb51c153c893d14e5bf8e5b7117` and its ONNX SHA-256 is verified
during the image build. If the Turkish model cannot be loaded or synthesized,
AVAROS falls back to the installed `espeak-ng` Turkish voice.

## License and permitted use

The `dfki` Piper model is trained from the DFKI OT Turkish speech database.
The dataset is Copyright 2009 DFKI GmbH and licensed under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
The model card is available in the
[Piper voice repository](https://huggingface.co/rhasspy/piper-voices/blob/main/tr/tr_TR/dfki/medium/MODEL_CARD).

This voice must not be used for commercial purposes without separate permission
from the rights holder. Confirm that the intended presentation/deployment is a
permitted non-commercial use, or obtain suitable permission, before deploying
an image that contains this model.

The historical `fahrettin` and `fettah` voices were not selected. Although their
model cards listed CC0 datasets, both voices were removed from the official
catalog at the contributors' request on 2025-12-30.
