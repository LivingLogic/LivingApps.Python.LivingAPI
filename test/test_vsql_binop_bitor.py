"""
Tests for the vSQL binary bitwise "or" operator ``A | B``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "repr(app.p_bool_false.value | False) == '0'")

def test_bool_bool2(config_data):
	check_vsql(config_data, "repr(app.p_bool_true.value | False) == '1'")

def test_bool_int1(config_data):
	check_vsql(config_data, "repr(app.p_bool_false.value | 0) == '0'")

def test_bool_int2(config_data):
	check_vsql(config_data, "repr(app.p_bool_true.value | 3) == '3'")

def test_int_bool1(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value | False) == '1777'")

def test_int_bool2(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value | True) == '1777'")

def test_int_int1(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value | 0b100111001) == '2041'")

def test_int_int2(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value | 0) == '1777'")

def test_int_int3(config_data):
	check_vsql(config_data, "repr((-app.p_int_value.value) | 0b100111001) == '-1729'")

def test_intset_intset1(config_data):
	check_vsql(config_data, "{1} | {1} == {1}")

def test_intset_intset2(config_data):
	check_vsql(config_data, "{1} | {2} == {2, 1}")

def test_numberset_numberset1(config_data):
	check_vsql(config_data, "{1.1} | {2.2} == {1.1, 2.2}")

def test_numberset_numberset2(config_data):
	check_vsql(config_data, "{1.1, 2.2} | {2.2, 3.3} == {1.1, 2.2, 3.3}")

def test_strset_strset1(config_data):
	check_vsql(config_data, "{'gurk'} | {'gurk'} == {'gurk'}")

def test_strset_strset2(config_data):
	check_vsql(config_data, "{'gurk', 'hurz'} | {'hinz', 'kunz'} == {'gurk', 'hurz', 'hinz', 'kunz'}")

def test_dateset_dateset1(config_data):
	check_vsql(config_data, "{@(2000-02-29)} | {@(2000-03-01)} == {@(2000-02-29), @(2000-03-01)}")

def test_dateset_dateset2(config_data):
	check_vsql(config_data, "{@(2000-02-29), @(2000-03-01)} | {@(2000-03-01), @(2000-03-02)} == {@(2000-02-29), @(2000-03-01), @(2000-03-02)}")

def test_datetimeset_datetimeset1(config_data):
	check_vsql(config_data, "{@(2000-02-29T12:34:56)} | {@(2000-03-01T12:34:56)} == {@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)}")

def test_datetimeset_datetimeset2(config_data):
	check_vsql(config_data, "{@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)} | {@(2000-03-01T12:34:56), @(2000-03-02T12:34:56)} == {@(2000-02-29T12:34:56), @(2000-03-01T12:34:56), @(2000-03-02T12:34:56)}")
