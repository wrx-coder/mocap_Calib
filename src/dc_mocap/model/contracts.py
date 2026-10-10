"""Versioned static products with explicit identity/frame/source metadata."""
from pathlib import Path
import csv
import numpy as np
import yaml


def truth(value):
    return str(value).lower() in ('true', '1', 'yes')


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('CSV_HEADER_MISSING')
        return list(reader)


def write_rows(path, rows, fields):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def meta_path(path):
    return Path(str(path) + '.meta.yaml')


def write_product(path, rows, metadata):
    required = ['sample_id', 'x_m', 'y_m', 'z_m', 'cov_xx', 'cov_yy', 'cov_zz', 'n_frames']
    if not rows:
        raise ValueError('EMPTY_PRODUCT')
    validate_product(rows, metadata)
    if Path(path).exists() or meta_path(path).exists():
        raise FileExistsError(path)
    write_rows(path, rows, required)
    meta_path(path).write_text(yaml.safe_dump(metadata, allow_unicode=True, sort_keys=True), encoding='utf-8')


def validate_product(rows, meta):
    if meta.get('schema_version') != 1 or meta.get('unit') != 'm':
        raise ValueError('PRODUCT_VERSION_OR_UNIT')
    if meta.get('source_kind') not in ('real', 'synthetic') or not meta.get('frame') or not meta.get('clock'):
        raise ValueError('PRODUCT_PROVENANCE_MISSING')
    if meta.get('quantity') not in ('surface', 'center') or not isinstance(meta.get('radius_compensated'), bool):
        raise ValueError('PRODUCT_QUANTITY_MISSING')
    if meta['quantity'] == 'surface' and meta['radius_compensated']:
        raise ValueError('DOUBLE_COMPENSATION')
    if not meta.get('provenance') or not rows:
        raise ValueError('PRODUCT_EMPTY_OR_NO_SOURCE')
    ids = [r['sample_id'] for r in rows]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('DUPLICATE_SAMPLE_ID')
    for r in rows:
        xyz = np.array([float(r[k]) for k in ('x_m','y_m','z_m')])
        cov = np.array([float(r[k]) for k in ('cov_xx','cov_yy','cov_zz')])
        if not np.isfinite(xyz).all() or not np.isfinite(cov).all() or (cov < 0).any() or int(r['n_frames']) < 1:
            raise ValueError('PRODUCT_INVALID_POINT_OR_COVARIANCE')


def read_product(path):
    rows = read_rows(path)
    with meta_path(path).open(encoding='utf-8') as f:
        meta = yaml.safe_load(f)
    if not isinstance(meta, dict):
        raise ValueError('PRODUCT_METADATA_MISSING')
    validate_product(rows, meta)
    return rows, meta


def paired_arrays(mocap_path, camera_path, pairs_path):
    mr, mm = read_product(mocap_path)
    cr, cm = read_product(camera_path)
    m = {r['sample_id']: r for r in mr}
    c = {r['sample_id']: r for r in cr}
    rows = [r for r in read_rows(pairs_path) if truth(r.get('valid', True))]
    ids = [r['sample_id'] for r in rows]
    mi = [r['mocap_segment_id'] for r in rows]
    ci = [r['camera_segment_id'] for r in rows]
    if not rows or len(set(ids)) != len(ids) or len(set(mi)) != len(mi) or len(set(ci)) != len(ci):
        raise ValueError('PAIR_ID_REUSED')
    for r in rows:
        if r['split'] not in ('train','validation') or r['mocap_segment_id'] not in m or r['camera_segment_id'] not in c:
            raise ValueError('PAIR_MISSING_OR_BAD_SPLIT')
    def xyz(table, key):
        return np.array([[float(table[r[key]][k]) for k in ('x_m','y_m','z_m')] for r in rows])
    a, b = xyz(c, 'camera_segment_id'), xyz(m, 'mocap_segment_id')
    # Camera covariance stays in C; approximate mocap uncertainty as
    # isotropic worst-axis variance so it is invariant to unknown rotation.
    variance = np.array([[float(c[r['camera_segment_id']][k]) + max(float(m[r['mocap_segment_id']][j]) for j in ('cov_xx','cov_yy','cov_zz')) for k in ('cov_xx','cov_yy','cov_zz')] for r in rows])
    return a, b, np.sqrt(np.maximum(variance, 1e-8)), np.array([r['split']=='train' for r in rows]), rows, mm, cm
