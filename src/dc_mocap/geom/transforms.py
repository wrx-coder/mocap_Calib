"""SE(3), column-vector convention T_A_B: B -> A."""
import numpy as np


def validate_transform(value):
    T = np.asarray(value, dtype=float)
    if T.shape != (4, 4) or not np.isfinite(T).all():
        raise ValueError('TRANSFORM_SHAPE_OR_NONFINITE')
    R = T[:3, :3]
    if not np.allclose(T[3], [0, 0, 0, 1], atol=1e-8, rtol=0):
        raise ValueError('TRANSFORM_LAST_ROW')
    if not np.allclose(R.T @ R, np.eye(3), atol=1e-7, rtol=0) or not np.isclose(np.linalg.det(R), 1, atol=1e-7):
        raise ValueError('TRANSFORM_NOT_RIGID')
    return T.copy()


def make_transform(rotation, translation):
    T = np.eye(4)
    T[:3, :3] = rotation
    T[:3, 3] = translation
    return validate_transform(T)


def transform_points(T, points):
    T = validate_transform(T)
    p = np.asarray(points, dtype=float)
    if p.ndim not in (1, 2) or p.shape[-1] != 3 or not np.isfinite(p).all():
        raise ValueError('INVALID_POINTS')
    return p @ T[:3, :3].T + T[:3, 3]


def transform_vectors(T, vectors):
    T = validate_transform(T)
    p = np.asarray(vectors, dtype=float)
    if p.ndim not in (1, 2) or p.shape[-1] != 3 or not np.isfinite(p).all():
        raise ValueError('INVALID_VECTORS')
    return p @ T[:3, :3].T


def inverse(T):
    T = validate_transform(T)
    return make_transform(T[:3, :3].T, -T[:3, :3].T @ T[:3, 3])


def compose(T_A_B, T_B_C):
    return validate_transform(validate_transform(T_A_B) @ validate_transform(T_B_C))


def change_basis(T_A_B, S_newA_A, S_newB_B=None):
    """Only change output basis by default; two-sided change is explicit."""
    S_A = make_transform(S_newA_A, [0, 0, 0])
    S_B = np.eye(4) if S_newB_B is None else make_transform(S_newB_B, [0, 0, 0])
    return compose(compose(S_A, T_A_B), inverse(S_B))
