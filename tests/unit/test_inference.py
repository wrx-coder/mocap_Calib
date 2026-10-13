"""Candidate inference is numerically useful but must not imply acceptance."""
import numpy as np
import pytest
from dc_calib.solver.inference import fit_similarity, fit_world_pnp, project_world
from dc_mocap.geom.transforms import make_transform, transform_points
from scipy.spatial.transform import Rotation


def test_similarity_recovers_units_rotation_translation():
    source = np.array([[0, 0, 0], [200, 0, 20], [-50, 300, 40], [0, -90, 180.]])
    T = make_transform(Rotation.from_euler('xyz', [.2, -.3, .5]).as_matrix(), [.1, .2, .3])
    target = transform_points(T, source * .00103)
    result = fit_similarity(source, target)
    assert result['scale'] == pytest.approx(.00103)
    assert np.allclose(result['T'], T, atol=1e-10)
    assert result['rmse_m'] < 1e-10
    assert 'status' not in result  # no hardware acceptance semantics


def test_planar_similarity_and_wrong_correspondences():
    a = np.array([[0, 0, 0], [1, 0, 0], [.2, .8, 0]])
    result = fit_similarity(a * 1000, a)
    assert result['scale'] == pytest.approx(.001)
    assert fit_similarity(a, a[[1, 0, 2]])['rmse_m'] > .03


@pytest.mark.parametrize('points', [np.zeros((3, 3)), np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]]),
                                   np.array([[0, 0, 0], [1, np.nan, 0], [0, 1, 0]])])
def test_invalid_similarity_rejected(points):
    with pytest.raises(ValueError):
        fit_similarity(points, points)


def test_multi_plane_world_pnp_and_projection_direction():
    pytest.importorskip('cv2')
    obj = np.array([[-.2, -.1, 0], [.2, -.1, 0], [.2, .1, 0], [-.2, .1, 0],
                    [-.1, .3, .3], [.15, .3, .3], [.15, .5, .25], [-.1, .5, .25]])
    T = make_transform(Rotation.from_euler('xyz', [.2, .3, -.1]).as_matrix(), [.1, -.1, 1.5])
    K = np.array([[600, 0, 320], [0, 605, 240], [0, 0, 1.]])
    uv = project_world(T, obj, K)
    fit = fit_world_pnp(obj, uv, K)
    assert fit['rmse_px'] < 1e-6
    assert np.allclose(fit['T'], T, atol=1e-7)
    with pytest.raises(ValueError, match='behind'):
        project_world(np.eye(4), [[0, 0, -1]], K)


def test_pnp_rejects_degenerate_and_nonfinite():
    pytest.importorskip('cv2')
    with pytest.raises(ValueError):
        fit_world_pnp(np.zeros((4, 3)), np.zeros((4, 2)), np.eye(3))
    with pytest.raises(ValueError):
        fit_world_pnp(np.ones((4, 3)), np.full((4, 2), np.nan), np.eye(3))
