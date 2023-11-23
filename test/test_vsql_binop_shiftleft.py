"""
Tests for the vSQL left shift operator ``<<``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_int_none.value << False is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value << True == 0")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value << True == 2")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value << 1 == 2")

def test_int_bool(config_data):
	check_vsql(config_data, "2 << app.p_bool_true.value == 4")

def test_int_int(config_data):
	check_vsql(config_data, "-app.p_int_value.value << 2 == -7108")
