"""
Tests for the vSQL binary operator ``and``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_null_bool(config_persons):
	check_vsql(config_persons, "(None and app.p_bool_true.value) is None")

def test_bool_null(config_persons):
	check_vsql(config_persons, "(app.p_bool_true.value and None) is None")

def test_bool_bool1(config_persons):
	check_vsql(config_persons, "(app.p_bool_true.value and app.p_bool_false.value) == False")

def test_bool_bool2(config_persons):
	check_vsql(config_persons, "(app.p_bool_true.value and app.p_bool_true.value) == True")

def test_int_int1(config_persons):
	check_vsql(config_persons, "(app.p_int_value.value and 0) == 0")

def test_int_int2(config_persons):
	check_vsql(config_persons, "(app.p_int_value.value and 42) == 42")

def test_number_number1(config_persons):
	check_vsql(config_persons, "(app.p_number_value.value and 0.0) == 0.0")

def test_number_number2(config_persons):
	check_vsql(config_persons, "(app.p_number_value.value and 42.5) == 42.5")

def test_str_str1(config_persons):
	check_vsql(config_persons, "(app.p_str_none.value and 'gurk') == ''")

def test_str_str2(config_persons):
	check_vsql(config_persons, "(app.p_str_value.value and 'hurz') == 'hurz'")

# def test_bool_bool3(config_persons):
# 	check_vsql(config_persons, "app.p_bool_true.value >> False == 1")

# def test_bool_bool4(config_persons):
# 	check_vsql(config_persons, "app.p_bool_true.value >> True == 0")

# def test_bool_int(config_persons):
# 	check_vsql(config_persons, "app.p_bool_true.value >> 1 == 0")

# def test_int_bool(config_persons):
# 	check_vsql(config_persons, "128 >> app.p_bool_true.value == 64")

# def test_int_int(config_persons):
# 	check_vsql(config_persons, "app.p_int_value.value >> 2 == 444")
