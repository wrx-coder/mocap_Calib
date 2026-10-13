"""Data-derived diagnostics, deliberately separate from hardware acceptance.

Similarity scale is metres per source unit. It is not proof of device units.
Image/world PnP preserves the exported World basis; it never invents torso.
"""
import numpy as np
from dc_mocap.geom.transforms import make_transform, transform_points


def fit_similarity(source, target):
    """Proper-rotation Umeyama fit, allowing planar but not collinear points."""
    a, b = np.asarray(source, float), np.asarray(target, float)
    if (a.shape != b.shape or a.ndim != 2 or a.shape[1] != 3 or len(a) < 3
            or not np.isfinite(a).all() or not np.isfinite(b).all()):
        raise ValueError('Need >=3 matched finite 3D points')
    ac, bc = a - a.mean(0), b - b.mean(0)
    if min(np.linalg.matrix_rank(ac), np.linalg.matrix_rank(bc)) < 2:
        raise ValueError('Collinear/coincident point set')
    u, _, vt = np.linalg.svd(ac.T @ bc)
    rotation = vt.T @ np.diag([1., 1., np.linalg.det(vt.T @ u.T)]) @ u.T
    scale = float(np.sum(bc * (ac @ rotation.T)) / np.sum(ac * ac))
    if scale <= 0:
        raise ValueError('Nonpositive scale')
    T = make_transform(rotation, b.mean(0) - scale * rotation @ a.mean(0))
    errors = np.linalg.norm(transform_points(T, scale * a) - b, axis=1)
    return {'T': T, 'scale': scale, 'errors_m': errors,
            'rmse_m': float(np.sqrt(np.mean(errors**2)))}


def fit_world_pnp(world, pixels, K):
    """Return T_C_W; optional OpenCV is imported only for this RGB diagnostic."""
    import cv2
    obj, uv, K = np.asarray(world, float), np.asarray(pixels, float), np.asarray(K, float)
    if (obj.ndim != 2 or obj.shape[1] != 3 or uv.shape != (len(obj), 2)
            or len(obj) < 4 or K.shape != (3, 3)
            or not all(np.isfinite(x).all() for x in (obj, uv, K))):
        raise ValueError('Need >=4 finite world/pixel pairs and a 3x3 K')
    if np.linalg.matrix_rank(obj - obj.mean(0)) < 2:
        raise ValueError('Degenerate PnP geometry')
    ok, r, t = cv2.solvePnP(obj, uv, K, None, flags=cv2.SOLVEPNP_SQPNP)
    if not ok:
        raise ValueError('PnP failed')
    ok, r, t = cv2.solvePnP(obj, uv, K, None, r, t, True, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        raise ValueError('PnP refinement failed')
    T = make_transform(cv2.Rodrigues(r)[0], t.ravel())
    if np.any(transform_points(T, obj)[:, 2] <= 0):
        raise ValueError('PnP points behind camera')
    predicted = cv2.projectPoints(obj, r, t, K, None)[0].reshape(-1, 2)
    errors = np.linalg.norm(predicted - uv, axis=1)
    return {'T': T, 'errors_px': errors,
            'rmse_px': float(np.sqrt(np.mean(errors**2)))}


def project_world(T_C_W, points, K):
    pc = transform_points(T_C_W, points)
    if np.any(pc[:, 2] <= 0):
        raise ValueError('Point behind camera')
    return (pc @ np.asarray(K, float).T)[:, :2] / pc[:, 2, None]
