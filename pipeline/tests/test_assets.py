"""T-PIPE-QUANT-01 (unit), T-PIPE-EXPR-01, Morton ordering."""

from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp

from atlas_pipeline import assets as a


def test_quant_round_trip_bounds() -> None:
    rng = np.random.default_rng(0)
    v = rng.uniform(-3.2, 22_500, 100_000)
    q = a.fit_quant(v.min(), v.max())
    err = np.abs(q.decode(q.encode(v)) - v).max()
    assert err <= q.scale / 2 + 1e-9
    assert err <= 0.5  # 22.5 mm TMA slide still under 0.5 µm
    assert q.encode(np.array([v.min() - 10, v.max() + 10])).tolist() == [0, 65535]


def test_morton_interleaves_bits() -> None:
    qx = np.array([0, 1, 0, 1, 65535], np.uint16)
    qy = np.array([0, 0, 1, 1, 65535], np.uint16)
    assert a.morton_code(qx, qy).tolist() == [0, 1, 2, 3, 0xFFFFFFFF]


@pytest.mark.parametrize("density", [0.0005, 0.05, 0.6])
def test_gene_encoder_round_trip_and_picks_smaller(density: float) -> None:
    rng = np.random.default_rng(1)
    n = 20_000
    idx = np.sort(rng.choice(n, int(n * density), replace=False))
    q = rng.integers(1, 256, len(idx)).astype(np.uint8)
    buf = a.encode_gene(n, idx, q)
    dense = np.zeros(n, np.uint8)
    dense[idx] = q
    assert np.array_equal(a.decode_gene(buf, n), dense)
    assert buf[0] == (1 if density < 0.3 else 0)
    assert len(buf) <= n + 5


def test_leb128_round_trip_large_values() -> None:
    vals = np.array([0, 1, 127, 128, 16383, 16384, 2**21, 2**28 + 5, 2**32 - 1], np.uint32)
    assert np.array_equal(a.unleb128(a.leb128(vals), len(vals)), vals)


def test_quantize_gene_reserves_zero() -> None:
    q, max_v = a.quantize_gene(np.array([1e-6, 0.5, 2.0]))
    assert max_v == 2.0 and q.tolist() == [1, 64, 255]
    q0, m0 = a.quantize_gene(np.zeros(0))
    assert m0 == 0.0 and q0.size == 0


def test_display_values_log1p_cp10k() -> None:
    counts = sp.csr_matrix(np.array([[1, 3], [0, 0], [2, 0]], np.int32))
    d = a.display_values(counts, 1e4).toarray()
    assert np.allclose(d[0], np.log1p(np.array([1, 3]) / 4 * 1e4))
    assert np.all(d[1] == 0)


def test_dumps_is_deterministic() -> None:
    obj = {"b": 1.0000000000123, "a": [np.float32(0.1), (1, 2)], "c": np.int64(3)}
    assert a.dumps(obj) == '{"a":[0.1000000015,[1,2]],"b":1.0,"c":3}'
