import numpy as np
import pytest
from dc_calib.camera.rgbd import extract_rgbd,surface_to_center
from dc_calib.solver.rigid import kabsch,fit_rigid
from dc_mocap.geom.transforms import transform_points,make_transform
from dc_mocap.io.fz_csv import read_mocap


def test_kabsch_and_no_double_compensation():
    rng=np.random.default_rng(1);a=rng.normal(size=(40,3))
    T=make_transform([[0,-1,0],[1,0,0],[0,0,1]],[.1,.2,.3])
    assert np.allclose(kabsch(a,transform_points(T,a)),T,atol=1e-12)
    with pytest.raises(ValueError):kabsch(np.ones((4,3)),np.ones((4,3)))
    with pytest.raises(ValueError):fit_rigid(a,a,quantity='center',radius_m=.04)


def test_rgbd_mask_and_real_intrinsics():
    camera=dict(resolution_px=[20,20],intrinsics=dict(fx=100,fy=100,cx=10,cy=10,distortion_model='none'),observation=dict(depth_unit=.001,depth_semantics='color_z',ball_radius_m=.04,ball_radius_already_compensated=False))
    mask=np.zeros((20,20),dtype=np.uint8);mask[8:13,8:13]=1
    result=extract_rgbd(np.full((20,20),1000),mask,camera,'center')
    assert np.isclose(result['z_m'],1.04)
    with pytest.raises(ValueError):extract_rgbd(np.zeros((20,20)),mask,camera)


def test_fz_header(tmp_path):
    path=tmp_path/'fz.csv'
    path.write_text('DataName,test,LengthUnits,mm\n\n,Type,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Marker,Marker,Marker,RigidBodyMarker,RigidBodyMarker,RigidBodyMarker\n,Name,chest,chest,chest,chest,chest,chest,chest,ball,ball,ball,template,template,template\n,ID,1,1,1,1,1,1,1,99,99,99,55,55,55\n,,Rotation,Rotation,Rotation,Rotation,Position,Position,Position,Position,Position,Position,Position,Position,Position\nFrame,Time,X,Y,Z,W,X,Y,Z,X,Y,Z,X,Y,Z\n1,0.01,0,0,0,1,100,0,0,200,100,1000,999,999,999\n2,0.02,0,0,0,1,100,0,0,,,,999,999,999\n')
    frames,meta=read_mocap(path,'chest',world_axis='Z_up')
    assert meta['unit']=='mm' and np.allclose(frames[0].markers['99'],[.2,.1,1.])
    assert frames[1].markers=={} and '55' not in frames[0].markers
    with pytest.raises(ValueError):read_mocap(path,'chest','m','Z_up')
