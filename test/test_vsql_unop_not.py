"""
Tests for the vSQL unary logical "not" operator ``not``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool1(config_data):
	check_vsql(config_data, "repr(not app.p_test_bool_none.value) == 'True'")

def test_bool2(config_data):
	check_vsql(config_data, "repr(not app.p_test_bool_false.value) == 'True'")

def test_bool3(config_data):
	check_vsql(config_data, "repr(not app.p_test_bool_true.value) == 'False'")

def test_int1(config_data):
	check_vsql(config_data, "repr(not app.p_test_int_none.value) == 'True'")

def test_int2(config_data):
	check_vsql(config_data, "repr(not app.p_test_int_value.value) == 'False'")

def test_number1(config_data):
	check_vsql(config_data, "repr(not app.p_test_number_none.value) == 'True'")

def test_number2(config_data):
	check_vsql(config_data, "repr(not app.p_test_number_value.value) == 'False'")

def test_str1(config_data):
	check_vsql(config_data, "repr(not app.p_test_str_none.value) == 'True'")

def test_str2(config_data):
	check_vsql(config_data, "repr(not app.p_test_str_value.value) == 'False'")

def test_date1(config_data):
	check_vsql(config_data, "repr(not app.p_test_date_none.value) == 'True'")

def test_date2(config_data):
	check_vsql(config_data, "repr(not app.p_test_date_value.value) == 'False'")

def test_datetime1(config_data):
	check_vsql(config_data, "repr(not app.p_test_datetime_none.value) == 'True'")

def test_datetime2(config_data):
	check_vsql(config_data, "repr(not app.p_test_datetime_value.value) == 'False'")

def test_datedelta1(config_data):
	check_vsql(config_data, "repr(not app.p_test_datedelta_none.value) == 'True'")

def test_datedelta2(config_data):
	check_vsql(config_data, "repr(not app.p_test_datedelta_value.value) == 'False'")

def test_datetimedelta1(config_data):
	check_vsql(config_data, "repr(not app.p_test_datetimedelta_none.value) == 'True'")

def test_datetimedelta2(config_data):
	check_vsql(config_data, "repr(not app.p_test_datetimedelta_value.value) == 'False'")

def test_monthdelta1(config_data):
	check_vsql(config_data, "repr(not app.p_test_monthdelta_none.value) == 'True'")

def test_monthdelta2(config_data):
	check_vsql(config_data, "repr(not app.p_test_monthdelta_value.value) == 'False'")

def test_color1(config_data):
	check_vsql(config_data, "repr(not app.p_test_color_none.value) == 'True'")

def test_color2(config_data):
	check_vsql(config_data, "repr(not app.p_test_color_value.value) == 'False'")

def test_geo(config_data):
	check_vsql(config_data, "repr(not geo(49, 11, 'Here')) == 'False'")
