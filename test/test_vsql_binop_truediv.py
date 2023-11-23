"""
Tests for the vSQL true division ``/``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_int_none.value / True is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value / True == 0")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value / True == 1")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value / 1 == 1")

def test_bool_number(config_data):
	check_vsql(config_data, "app.p_bool_true.value / 0.5 == 2.0")

def test_int_bool(config_data):
	check_vsql(config_data, "2 / app.p_bool_true.value == 2")

def test_int_int(config_data):
	check_vsql(config_data, "app.p_int_value.value / 2 == 888.5")

def test_int_number(config_data):
	check_vsql(config_data, "85 / app.p_number_value.value == 2.0")

def test_number_bool(config_data):
	check_vsql(config_data, "app.p_number_value.value / app.p_bool_true.value == 42.5")

def test_number_int(config_data):
	check_vsql(config_data, "app.p_number_value.value / 2 == 21.25")

def test_number_number(config_data):
	check_vsql(config_data, "app.p_number_value.value / 0.5 == 85.0")

def test_datetimedelta_bool(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value / True == app.p_datetimedelta_value.value")

def test_datetimedelta_int(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value / 2 == timedelta(0, (18 * 60 + 17) * 60 + 28)")

def test_datetimedelta_number(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value / 12.5 == timedelta(0, (2 * 60 + 55) * 60 + 36)")
