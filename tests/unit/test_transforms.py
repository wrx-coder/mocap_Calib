import numpy as np
import pytest
from dc_mocap.geom.transforms import *
from dc_mocap.geom.rotations import quaternion_to_matrix


def test_known_direction_and_inverse():
    R=np.array([[0,-1,0],[1,0,0],[0,0,1.]])
    T=make_transform(R,[1,2,3])
    assert np.allclose(transform_points(T,[1,0,0]),[1,3,3])
    assert np.allclose(transform_vectors(T,[1,0,0]),[0,1,0])
    assert np.allclose(transform_points(inverse(T),[1,3,3]),[1,0,0])
    assert np.allclose(change_basis(T,R),make_transform(R@R,R@[1,2,3]))
    q=[0,0,np.sqrt(.5),np.sqrt(.5)]
    assert np.allclose(quaternion_to_matrix(q),quaternion_to_matrix(-np.array(q)))


@pytest.mark.parametrize('bad',[np.diag([2,1,1,1]),np.diag([-1,1,1,1]),np.full((4,4),np.nan),np.eye(3)])
def test_bad_rigid(bad):
    with pytest.raises(ValueError):validate_transform(bad)
