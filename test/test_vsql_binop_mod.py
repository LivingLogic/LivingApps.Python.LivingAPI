"""
Tests for the vSQL modulo operator ``%``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_bool_none.value % True is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value % True == 0")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value % True == 0")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value % 1 == 0")

def test_bool_number(config_data):
	check_vsql(config_data, "app.p_bool_true.value % 0.3 == 0.1")

def test_int_bool(config_data):
	check_vsql(config_data, "2 % app.p_bool_true.value == 0")

def test_int_int(config_data):
	check_vsql(config_data, "app.p_int_value.value % 2 == 1")

def test_int_number(config_data):
	check_vsql(config_data, "86 % app.p_number_value.value == 1")

def test_number_bool(config_data):
	check_vsql(config_data, "app.p_number_value.value % app.p_bool_true.value == 0.5")

def test_number_int(config_data):
	check_vsql(config_data, "app.p_number_value.value % 4 == 2.5")

def test_number_number1(config_data):
	check_vsql(config_data, "app.p_number_value.value % 3.5 == 0.5")

def test_number_number2(config_data):
	check_vsql(config_data, "app.p_number_value.value % -3.5 == -3.0")

def test_number_number3(config_data):
	check_vsql(config_data, "-app.p_number_value.value % 3.5 == 3.0")

def test_number_number4(config_data):
	check_vsql(config_data, "-app.p_number_value.value % -3.5 == -0.5")

def test_color_color1(config_data):
	check_vsql(config_data, "#000 % app.p_color_value.value == #000")

def test_color_color2(config_data):
	check_vsql(config_data, "app.p_color_value.value % #000 == #28517a")

def test_color_color3(config_data):
	check_vsql(config_data, "#80808080 % rgb(1, 1, 1) == #bfbfbf")
