"""
Tests for the vSQL binary operator ``or``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_null_bool(config_persons):
	check_vsql(config_persons, "(None or app.p_bool_true.value) == app.p_bool_true.value")

def test_bool_null(config_persons):
	check_vsql(config_persons, "(app.p_bool_true.value or None) == app.p_bool_true.value")

def test_bool_bool1(config_persons):
	check_vsql(config_persons, "(app.p_bool_false.value or app.p_bool_false.value) == False")

def test_bool_bool2(config_persons):
	check_vsql(config_persons, "(app.p_bool_true.value or app.p_bool_false.value) == True")

def test_int_int1(config_persons):
	check_vsql(config_persons, "(0 or app.p_int_value.value) == app.p_int_value.value")

def test_int_int2(config_persons):
	check_vsql(config_persons, "(42 or app.p_int_value.value) == 42")

def test_number_number1(config_persons):
	check_vsql(config_persons, "(0.0 or app.p_number_value.value) == app.p_number_value.value")

def test_number_number2(config_persons):
	check_vsql(config_persons, "(42.5 or app.p_number_value.value) == 42.5")

def test_str_str1(config_persons):
	check_vsql(config_persons, "('' or app.p_str_value.value) == app.p_str_value.value")

def test_str_str2(config_persons):
	check_vsql(config_persons, "('hurz' or app.p_str_value.value) == 'hurz'")

def test_date_date1(config_persons):
	check_vsql(config_persons, "(@(2000-02-20) or app.p_date_none.value) == @(2000-02-20)")

def test_date_date2(config_persons):
	check_vsql(config_persons, "(@(2000-02-20) or app.p_date_value.value) == @(2000-02-20)")

def test_datetime_datetime1(config_persons):
	check_vsql(config_persons, "(app.p_datetime_none.value or @(2000-02-20T12:34:56)) == @(2000-02-20T12:34:56)")

def test_datetime_datetime2(config_persons):
	check_vsql(config_persons, "(app.p_datetime_value.value or @(2000-02-20T12:34:56)) == app.p_datetime_value.value")

def test_datedelta_datedelta1(config_persons):
	check_vsql(config_persons, "(app.p_datedelta_none.value or days(10)) == days(10)")

def test_datedelta_datedelta2(config_persons):
	check_vsql(config_persons, "(app.p_datedelta_value.value or days(10)) == app.p_datedelta_value.value")

def test_datetimedelta_datetimedelta1(config_persons):
	check_vsql(config_persons, "(app.p_datetimedelta_none.value or hours(12)) == hours(12)")

def test_datetimedelta_datetimedelta2(config_persons):
	check_vsql(config_persons, "(app.p_datetimedelta_value.value or hours(12)) == app.p_datetimedelta_value.value")

def test_intlist_intlist1(config_persons):
	check_vsql(config_persons, "(0*[1] or [4, 5, 6]) == [4, 5, 6]")

def test_intlist_intlist2(config_persons):
	check_vsql(config_persons, "([1, 2, 3] or [4, 5, 6]) == [1, 2, 3]")

def test_numberlist_numberlist1(config_persons):
	check_vsql(config_persons, "(0*[1.1] or [4.4, 5.5, 6.6]) == [4.4, 5.5, 6.6]")

def test_numberlist_numberlist2(config_persons):
	check_vsql(config_persons, "([1.1, 2.2, 3.3] or [4.4, 5.5, 6.6]) == [1.1, 2.2, 3.3]")

