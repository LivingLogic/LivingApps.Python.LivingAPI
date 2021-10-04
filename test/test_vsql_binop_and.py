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

def test_date_date1(config_persons):
	check_vsql(config_persons, "(app.p_date_none.value and @(2000-02-20)) is None")

def test_date_date2(config_persons):
	check_vsql(config_persons, "(app.p_date_value.value and @(2000-02-20)) == @(2000-02-20)")

def test_datetime_datetime1(config_persons):
	check_vsql(config_persons, "(app.p_datetime_none.value and @(2000-02-20T12:34:56)) is None")

def test_datetime_datetime2(config_persons):
	check_vsql(config_persons, "(app.p_datetime_value.value and @(2000-02-20T12:34:56)) == @(2000-02-20T12:34:56)")

def test_datedelta_datedelta1(config_persons):
	check_vsql(config_persons, "(app.p_datedelta_none.value and days(10)) is None")

def test_datedelta_datedelta2(config_persons):
	check_vsql(config_persons, "(app.p_datedelta_value.value and days(10)) == days(10)")

def test_datetimedelta_datetimedelta1(config_persons):
	check_vsql(config_persons, "(app.p_datetimedelta_none.value and hours(12)) is None")

def test_datetimedelta_datetimedelta2(config_persons):
	check_vsql(config_persons, "(app.p_datetimedelta_value.value and hours(12)) == hours(12)")

def test_intlist_intlist1(config_persons):
	check_vsql(config_persons, "(0*[1] and [4, 5, 6]) == 0*[1]")

def test_intlist_intlist2(config_persons):
	check_vsql(config_persons, "([1, 2, 3] and [4, 5, 6]) == [4, 5, 6]")

def test_numberlist_numberlist1(config_persons):
	check_vsql(config_persons, "(0*[1.1] and [4.4, 5.5, 6.6]) == 0*[1.1]")

def test_numberlist_numberlist2(config_persons):
	check_vsql(config_persons, "([1.1, 2.2, 3.3] and [4.4, 5.5, 6.6]) == [4.4, 5.5, 6.6]")

