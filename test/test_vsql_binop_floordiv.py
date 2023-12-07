"""
Tests for the vSQL floor division ``//``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_int_none.value // True is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value // True == 0")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value // True == 1")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value // 1 == 1")

def test_bool_number(config_data):
	check_vsql(config_data, "app.p_bool_true.value // 0.5 == 2")

def test_int_bool(config_data):
	check_vsql(config_data, "2 // app.p_bool_true.value == 2")

def test_int_int(config_data):
	check_vsql(config_data, "app.p_int_value.value // 2 == 888")

def test_int_number(config_data):
	check_vsql(config_data, "85 // app.p_number_value.value == 2")

def test_number_bool(config_data):
	check_vsql(config_data, "app.p_number_value.value // app.p_bool_true.value == 42")

def test_number_int(config_data):
	check_vsql(config_data, "app.p_number_value.value // 2 == 21")

def test_number_number(config_data):
	check_vsql(config_data, "app.p_number_value.value // 3.5 == 12")

def test_datedelta_bool(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value // True == days(12)")

def test_datedelta_int(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value // 5 == days(2)")

def test_monthdelta_bool(config_data):
	check_vsql(config_data, "app.p_monthdelta_value.value // True == months(3)")

def test_monthdelta_int(config_data):
	check_vsql(config_data, "app.p_monthdelta_value.value // 2 == months(1)")

def test_datetimedelta_bool(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value // True == days(1)")

def test_datetimedelta_int(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value // 2 == days(0)")

def test_datetimedelta_number(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value // 12.5 == days(0)")
