import pytest
from dc_mocap.model.contracts import validate_product


def test_duplicate_and_negative_covariance():
    r=dict(sample_id='a',x_m=1,y_m=2,z_m=3,cov_xx=0,cov_yy=0,cov_zz=0,n_frames=4)
    m=dict(schema_version=1,unit='m',frame='C',clock='c',source_kind='real',quantity='center',radius_compensated=True,provenance={'file':'test'})
    validate_product([r],m)
    with pytest.raises(ValueError):validate_product([r,r],m)
    with pytest.raises(ValueError):validate_product([{**r,'cov_zz':-1}],m)
    with pytest.raises(ValueError):validate_product([r],{**m,'quantity':'surface'})
