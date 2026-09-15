from pathlib import Path
from types import SimpleNamespace

import pytest

from radar.local_bge import LocalBgeM3Provider


def test_dense_embedding_uses_cls_and_a_distinct_profile() -> None:
    np = pytest.importorskip("numpy")
    hidden = np.zeros((1, 2, 1024), dtype=np.float32)
    hidden[0, 0, :2] = [3, 4]
    # A large non-CLS token must not contaminate the dense embedding.
    hidden[0, 1, 2] = 100
    tokenizer = SimpleNamespace(
        encode=lambda text: SimpleNamespace(ids=[0, 2], attention_mask=[1, 1])
    )
    runtime = SimpleNamespace(
        get_inputs=lambda: [
            SimpleNamespace(name="input_ids"),
            SimpleNamespace(name="attention_mask"),
        ],
        run=lambda output_names, inputs: [hidden],
    )
    provider = LocalBgeM3Provider(Path("unused-test-artifacts"), "test-revision")
    provider._runtime = (np, tokenizer, runtime)
    vector = provider._embed("测试")
    assert vector[:2] == pytest.approx([0.6, 0.8])
    assert vector[2:] == [0.0] * 1022
    assert provider.profile.input_template_version == "plain-cls512-v2"
