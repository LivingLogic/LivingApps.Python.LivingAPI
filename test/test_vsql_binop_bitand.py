"""
Tests for the vSQL binary bitwise "and" operator ``A & B``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "repr(app.p_bool_false.value & True) == '0'")

def test_bool_bool2(config_data):
	check_vsql(config_data, "repr(app.p_bool_true.value & True) == '1'")

def test_bool_int1(config_data):
	check_vsql(config_data, "repr(app.p_bool_false.value & 3) == '0'")

def test_bool_int2(config_data):
	check_vsql(config_data, "repr(app.p_bool_true.value & 3) == '1'")

def test_int_bool1(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value & False) == '0'")

def test_int_bool2(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value & True) == '1'")

def test_int_int1(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value & 0b100111001) == '49'")

def test_int_int2(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value & 0b100001110) == '0'")

def test_int_int3(config_data):
	check_vsql(config_data, "repr((-app.p_int_value.value) & 0b100111001) == '265'")

def test_intset_intset1(config_data):
	check_vsql(config_data, "repr({1} & {2}) == '{}'")

def test_intset_intset2(config_data):
	check_vsql(config_data, "repr({1, 2} & {2, 3}) == '{2}'")

def test_numberset_numberset1(config_data):
	check_vsql(config_data, "repr({1.1} & {2.2}) == '{}'")

def test_numberset_numberset2(config_data):
	check_vsql(config_data, "repr({1.1, 2.2} & {2.2, 3.3}) == '{2.2}'")

def test_strset_strset1(config_data):
	check_vsql(config_data, "repr({'gurk', 'hurz'} & {'hinz', 'kunz'}) == '{}'")

def test_strset_strset2(config_data):
	check_vsql(config_data, "repr({'gurk', 'hurz'} & {'hurz', 'kunz'}) == '{\\'hurz\\'}'")

def test_dateset_dateset1(config_data):
	check_vsql(config_data, "repr({@(2000-02-29), @(2000-03-01)} & {@(2000-03-02), @(2000-03-03)}) == '{}'")

def test_dateset_dateset2(config_data):
	check_vsql(config_data, "repr({@(2000-02-29), @(2000-03-01)} & {@(2000-03-01), @(2000-03-02)}) == '{@(2000-03-01)}'")

def test_datetimeset_datetimeset1(config_data):
	check_vsql(config_data, "repr({@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)} & {@(2000-03-02T12:34:56), @(2000-03-03T12:34:56)}) == '{}'")

def test_datetimeset_datetimeset2(config_data):
	check_vsql(config_data, "repr({@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)} & {@(2000-03-01T12:34:56), @(2000-03-02T12:34:56)}) == '{@(2000-03-01T12:34:56)}'")
