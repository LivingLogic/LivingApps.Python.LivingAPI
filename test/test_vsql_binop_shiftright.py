"""
Tests for the vSQL right shift operator ``>>``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_persons):
	check_vsql(config_persons, "app.p_bool_none.value >> False is None")

def test_bool_bool2(config_persons):
	check_vsql(config_persons, "app.p_bool_false.value >> True == 0")

def test_bool_bool3(config_persons):
	check_vsql(config_persons, "app.p_bool_true.value >> False == 1")

def test_bool_bool4(config_persons):
	check_vsql(config_persons, "app.p_bool_true.value >> True == 0")

def test_bool_int(config_persons):
	check_vsql(config_persons, "app.p_bool_true.value >> 1 == 0")

def test_int_bool(config_persons):
	check_vsql(config_persons, "128 >> app.p_bool_true.value == 64")

def test_int_int(config_persons):
	check_vsql(config_persons, "app.p_int_value.value >> 2 == 444")
