"""
Tests for the vSQL binary bitwise "exclusive or" operator ``A ^ B``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "repr(app.p_bool_false.value ^ False) == '0'")

def test_bool_bool2(config_data):
	check_vsql(config_data, "repr(app.p_bool_false.value ^ True) == '1'")

def test_bool_int(config_data):
	check_vsql(config_data, "repr(app.p_bool_true.value ^ 3) == '2'")

def test_int_bool(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value ^ True) == '1776'")

def test_int_int1(config_data):
	check_vsql(config_data, "repr(app.p_int_value.value ^ 0b100111001) == '1992'")

def test_int_int2(config_data):
	check_vsql(config_data, "repr((-app.p_int_value.value) ^ 0b100111001) == '-1994'")

