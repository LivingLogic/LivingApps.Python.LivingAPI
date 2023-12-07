"""
Tests for the vSQL unary negation operator ``-``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool1(config_data):
	check_vsql(config_data, "repr(-app.p_bool_none.value) == 'None'")

def test_bool2(config_data):
	check_vsql(config_data, "repr(-app.p_bool_false.value) == '0'")

def test_bool3(config_data):
	check_vsql(config_data, "repr(-app.p_bool_true.value) == '-1'")

def test_int1(config_data):
	check_vsql(config_data, "repr(-app.p_int_none.value) == 'None'")

def test_int2(config_data):
	check_vsql(config_data, "repr(-app.p_int_value.value) == '-1777'")

def test_number1(config_data):
	check_vsql(config_data, "repr(-app.p_number_none.value) == 'None'")

def test_number2(config_data):
	check_vsql(config_data, "repr(-app.p_number_value.value) == '-42.5'")

def test_datedelta1(config_data):
	check_vsql(config_data, "repr(-app.p_datedelta_none.value) == 'None'")

def test_datedelta2(config_data):
	check_vsql(config_data, "repr(-app.p_datedelta_value.value) == 'timedelta(-12)'")

def test_datetimedelta1(config_data):
	check_vsql(config_data, "repr(-app.p_datetimedelta_none.value) == 'None'")

def test_datetimedelta2(config_data):
	check_vsql(config_data, "repr(-app.p_datetimedelta_value.value) == 'timedelta(-2, 41104)'")

def test_monthdelta1(config_data):
	check_vsql(config_data, "repr(-app.p_monthdelta_none.value) == 'None'")

def test_monthdelta2(config_data):
	check_vsql(config_data, "repr(-app.p_monthdelta_value.value) == 'monthdelta(-3)'")
