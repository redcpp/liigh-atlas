"""One-command pipeline: adapt → validate → persist canonical → build assets → checks → manifest."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from . import align, canonical_io, logs
from .adapters import get_adapter
from .adapters.fixture import FIXTURE_DIR
from .assets import build_assets, dumps, write_manifest
from .config import DatasetConfig, load_config
from .contract import CanonicalDataset, require_valid
from .env import REPO_ROOT, build_dir, canonical_dir, data_root, raw_dir
from .he import Pyramid, SourceImage, TileReader, build_pyramid, thumbnail
from .rawio import RawFileLog

log = logging.getLogger("atlas_pipeline")
QUANT_MAX_UM = 0.5
QUANT_MAX_FRAC = 0.001


class BuildCheckError(RuntimeError):
    pass


@dataclass
class RunSummary:
    name: str
    release: str
    out_dir: Path
    counts: dict[str, Any]
    sizes: dict[str, dict[str, int]]
    quant_errors: dict[str, float]
    align: list[align.AlignSuite] = field(default_factory=list)
    raw_log: str = ""
    validation: str = ""
    seconds: float = 0.0

    def render(self) -> str:
        c = self.counts
        lines = [
            f"== {self.name} release {self.release} ({self.seconds:.0f} s) -> {self.out_dir}",
            "Canonical data contract: VALID",
            self.validation,
            f"cells = {c['cells']}",
            f"median transcripts per cell = {c['median_transcripts']:g}",
            f"genes = {c['genes']}",
            f"clusters = {c['clusters']}",
            f"sections = {c['sections']}  cores = {c['cores']}  patients = {c['patients']}",
            "Quantization max round-trip error (T-PIPE-QUANT-01): "
            + ", ".join(f"{k} = {v:.3g}" for k, v in self.quant_errors.items())
            + f"  (limits: {QUANT_MAX_UM} µm, {QUANT_MAX_FRAC:.1%} of UMAP range)",
            "Asset sizes per family:",
        ]
        total_f = total_b = 0
        for fam, s in self.sizes.items():
            lines.append(f"  {fam:<12} {s['files']:>7} files {s['bytes'] / 1e6:>10.2f} MB")
            total_f += s["files"]
            total_b += s["bytes"]
        lines.append(f"  {'TOTAL':<12} {total_f:>7} files {total_b / 1e6:>10.2f} MB  (NFR-13 budget 5000 MB)")
        lines += [a.render() for a in self.align]
        lines.append(self.raw_log)
        return "\n".join(lines)


def out_root(cfg: DatasetConfig) -> Path:
    """Fixture builds stay inside the repo (gitignored ``.build/``); everything else on $DATA_ROOT."""
    return REPO_ROOT / ".build" / cfg.name if cfg.name == "fixture" else build_dir(cfg.name)


def raw_root(cfg: DatasetConfig) -> Path:
    return FIXTURE_DIR if cfg.adapter == "fixture" else raw_dir(cfg.source or cfg.name)


def run(name: str) -> RunSummary:
    t0 = time.time()
    cfg = load_config(name)
    if cfg.name != "fixture":
        data_root()  # refuse early when the data volume is not mounted
    out = out_root(cfg)
    flt = logs.setup(out / "pipeline.log", private=cfg.visibility == "private")
    rawlog = RawFileLog()
    log.info("adapter %s", cfg.adapter)
    ds = get_adapter(cfg.adapter)(cfg, rawlog)
    report = require_valid(ds, cfg)
    log.info("canonical contract valid (%d checks)", len(report.checks))
    canon = out / "canonical" if cfg.name == "fixture" else canonical_dir(cfg.name)
    canonical_io.save(ds, canon)

    staging = out / "_staging"
    res = build_assets(ds, staging, cfg.scale_factor)
    for k, v in res.quant_errors.items():
        limit = QUANT_MAX_UM if k.startswith("xy") else QUANT_MAX_FRAC
        if not v <= limit:
            raise BuildCheckError(f"quantization error {k} = {v} exceeds {limit}")

    results: list[align.AlignSuite] = []
    if cfg.he:
        results = build_he(ds, cfg, res, rawlog)
    manifest = write_manifest(res, ds)
    total = sum(s["bytes"] for s in manifest["sizes"].values())
    if total > cfg.max_total_bytes:
        raise BuildCheckError(f"assets total {total} B exceed the NFR-13 budget {cfg.max_total_bytes} B")
    final = out / manifest["release"]
    if final.exists():
        shutil.rmtree(final)
    staging.rename(final)
    (out / "current.json").write_text(json.dumps({"release": manifest["release"]}))
    if rawlog.forbidden_opened():
        raise BuildCheckError("a forbidden raw file was opened")
    log.info("release %s written to %s", manifest["release"], final)
    if flt.rejected:
        log.info("privacy filter rejected %d cell-level log records", flt.rejected)
    return RunSummary(
        name=cfg.name,
        release=manifest["release"],
        out_dir=final,
        counts={**manifest["counts"], "median_transcripts": float(np.median(ds.cells.n_transcripts))},
        sizes=manifest["sizes"],
        quant_errors=res.quant_errors,
        align=results,
        raw_log=rawlog.render(),
        validation=report.render(),
        seconds=time.time() - t0,
    )


def build_he(ds: CanonicalDataset, cfg: DatasetConfig, res: Any, rawlog: RawFileLog) -> list[align.AlignSuite]:
    results: list[align.AlignSuite] = []
    w = res.writer
    sec: Any
    core: Any
    for sec in ds.sections.itertuples():
        if sec.he_image is None:
            log.info("section %s: no H&E (Core Detail shows 'H&E not available')", sec.section_id)
            continue
        src = SourceImage(rawlog.use(raw_root(cfg) / str(sec.he_image)))
        m = np.asarray(sec.affine, float).reshape(3, 3)
        he_px = float(sec.he_pixel_size_um)
        for core in ds.cores[ds.cores.section_id == sec.section_id].sort_values("core_id").itertuples():
            pyr = Pyramid.fit((core.bbox_x0, core.bbox_y0, core.bbox_x1, core.bbox_y1), he_px)
            prefix = f"he/{sec.section_id}/{core.core_id}"
            log.info(
                "H&E %s: %d levels, full res %.3f µm/px (source %.4f), %dx%d px",
                prefix,
                pyr.nz,
                pyr.px_um,
                he_px,
                *pyr.level_size(pyr.nz - 1),
            )
            build_pyramid(src, m, he_px, pyr, prefix, lambda rel, data: w.write(rel, data, "he"))
            w.json(f"{prefix}/pyramid.json", pyr.meta(), "he-meta")
            w.write(f"thumbs/{core.core_id}.webp", thumbnail(src, m, he_px, pyr), "thumbs")
        if cfg.align_test:
            results += alignment_tests(ds, sec, src, m, he_px, res.staging, cfg.seed)
    for r in results:
        log.info(r.render())
        if not r.passed:
            raise BuildCheckError(f"alignment test failed: {r.render()}")
    return results


def alignment_tests(
    ds: CanonicalDataset, sec: Any, src: SourceImage, m: NDArray[Any], he_px: float, staging: Path, seed: int
) -> list[align.AlignSuite]:
    cells = ds.cells[ds.cells.section_id == sec.section_id]
    xy = cells[["x_um", "y_um"]].to_numpy()
    rand = align.random_points(src, m, he_px, xy, np.random.default_rng(seed))
    sample_raw, _ = align.raw_sampler(src, m, he_px)
    r1 = align.run_suite(
        f"T-PIPE-ALIGN-01 raw H&E [{sec.section_id}]", sample_raw, xy, rand, np.random.default_rng(seed)
    )
    # T-PIPE-ALIGN-02: same points, sampled from the pre-aligned full-resolution tiles by µm position
    readers = {}
    for core in ds.cores[ds.cores.section_id == sec.section_id].itertuples():
        pdir = staging / f"he/{sec.section_id}/{core.core_id}"
        readers[core.core_id] = (core, TileReader(pdir, json.loads((pdir / "pyramid.json").read_text())))
    rpx = max(1, round(align.DISK_UM / next(iter(readers.values()))[1].px))
    disk = align.disk(rpx)

    def sample_pyr(x: float, y: float) -> float:
        for core, rd in readers.values():
            if core.bbox_x0 - 50 <= x <= core.bbox_x1 + 50 and core.bbox_y0 - 50 <= y <= core.bbox_y1 + 50:
                return float(align.hematoxylin(rd.patch(x, y, rpx))[disk].mean())
        return float(align.hematoxylin(np.full((1, 1, 3), 255, np.uint8)).mean())

    r2 = align.run_suite(
        f"T-PIPE-ALIGN-02 pre-aligned pyramid [{sec.section_id}]",
        sample_pyr,
        xy,
        rand,
        np.random.default_rng(seed),
    )
    return [r1, r2]


def tree_hashes(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def repro(name: str) -> tuple[bool, str]:
    """T-PIPE-REPRO-01: two full runs, compare every asset hash."""
    s1 = run(name)
    h1 = tree_hashes(s1.out_dir)
    first = s1.out_dir.with_name(s1.out_dir.name + "-run1")
    if first.exists():
        shutil.rmtree(first)
    s1.out_dir.rename(first)
    s2 = run(name)
    h2 = tree_hashes(s2.out_dir)
    shutil.rmtree(first)
    diff = sorted(k for k in set(h1) | set(h2) if h1.get(k) != h2.get(k))
    agg1 = hashlib.sha256(dumps(h1).encode()).hexdigest()
    agg2 = hashlib.sha256(dumps(h2).encode()).hexdigest()
    lines = [
        s2.render(),
        "== T-PIPE-REPRO-01",
        f"run 1: release {s1.release}, {len(h1)} files, sha256(all file hashes) = {agg1}",
        f"run 2: release {s2.release}, {len(h2)} files, sha256(all file hashes) = {agg2}",
        f"manifest.json sha256: run1 {h1.get('manifest.json')} run2 {h2.get('manifest.json')}",
        f"differing files: {len(diff)}" + (f" e.g. {diff[:5]}" if diff else ""),
        "IDENTICAL" if not diff else "DIFFERENT",
    ]
    return not diff, "\n".join(lines)
