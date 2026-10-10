"""Quaternion boundaries are xyzw, never component-wise averaged."""
import numpy as np
from scipy.spatial.transform import Rotation


def normalize_quaternion(q):
    q = np.asarray(q, dtype=float)
    if q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q) < 1e-12:
        raise ValueError('INVALID_QUATERNION')
    return q / np.linalg.norm(q)


def quaternion_to_matrix(q):
    return Rotation.from_quat(normalize_quaternion(q)).as_matrix()


def matrix_to_quaternion(R):
    from .transforms import make_transform
    return Rotation.from_matrix(make_transform(R, [0, 0, 0])[:3, :3]).as_quat()


def rotation_difference_deg(R1, R2):
    from .transforms import make_transform
    a = make_transform(R1, [0, 0, 0])[:3, :3]
    b = make_transform(R2, [0, 0, 0])[:3, :3]
    return float(np.degrees(Rotation.from_matrix(a.T @ b).magnitude()))
