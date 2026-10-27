"""Launch mlx_lm.lora with the chat template in non-thinking mode.

mlx-lm renders training samples with thinking enabled by default. For Qwen3.8
that injects a hidden "Reasoning effort is set to xhigh..." system text and puts
the prompt mask before the empty <think></think> block, so training would not
match how the model is prompted at inference (thinking off). This launcher
makes enable_thinking=False the default and then hands over to mlx_lm.lora.

Runs in the training environment (.venv-train, mlx-lm installed):

  .venv-train/bin/python -m commodore38.train.lora -c train/configs/proefrun.yaml
"""

from __future__ import annotations

import sys

from mlx_lm import lora
from mlx_lm.tokenizer_utils import TokenizerWrapper

_original = TokenizerWrapper.apply_chat_template


def _apply_chat_template(self, *args, **kwargs):
    kwargs.setdefault("enable_thinking", False)
    return _original(self, *args, **kwargs)


TokenizerWrapper.apply_chat_template = _apply_chat_template

if __name__ == "__main__":
    sys.argv[0] = "mlx_lm.lora"
    lora.main()
