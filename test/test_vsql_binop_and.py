"""
Tests for the vSQL binary operator ``and``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

d1 = "@(2000-02-29)"
d2 = "@(2000-03-01)"

dt1 = "@(2000-02-29T12:34:56)"
dt2 = "@(2000-03-01T12:34:56)"

def test_null_bool(config_data):
	check_vsql(config_data, "(None and app.p_bool_true.value) is None")

def test_bool_null(config_data):
	check_vsql(config_data, "(app.p_bool_true.value and None) is None")

def test_bool_bool1(config_data):
	check_vsql(config_data, "(app.p_bool_true.value and app.p_bool_false.value) == False")

def test_bool_bool2(config_data):
	check_vsql(config_data, "(app.p_bool_true.value and app.p_bool_true.value) == True")

def test_int_int1(config_data):
	check_vsql(config_data, "(app.p_int_value.value and 0) == 0")

def test_int_int2(config_data):
	check_vsql(config_data, "(app.p_int_value.value and 42) == 42")

def test_number_number1(config_data):
	check_vsql(config_data, "(app.p_number_value.value and 0.0) == 0.0")

def test_number_number2(config_data):
	check_vsql(config_data, "(app.p_number_value.value and 42.5) == 42.5")

def test_str_str1(config_data):
	check_vsql(config_data, "(app.p_str_none.value and 'gurk') == ''")

def test_str_str2(config_data):
	check_vsql(config_data, "(app.p_str_value.value and 'hurz') == 'hurz'")

def test_date_date1(config_data):
	check_vsql(config_data, "(app.p_date_none.value and @(2000-02-20)) is None")

def test_date_date2(config_data):
	check_vsql(config_data, "(app.p_date_value.value and @(2000-02-20)) == @(2000-02-20)")

def test_datetime_datetime1(config_data):
	check_vsql(config_data, "(app.p_datetime_none.value and @(2000-02-20T12:34:56)) is None")

def test_datetime_datetime2(config_data):
	check_vsql(config_data, "(app.p_datetime_value.value and @(2000-02-20T12:34:56)) == @(2000-02-20T12:34:56)")

def test_datedelta_datedelta1(config_data):
	check_vsql(config_data, "(app.p_datedelta_none.value and days(10)) is None")

def test_datedelta_datedelta2(config_data):
	check_vsql(config_data, "(app.p_datedelta_value.value and days(10)) == days(10)")

def test_datetimedelta_datetimedelta1(config_data):
	check_vsql(config_data, "(app.p_datetimedelta_none.value and hours(12)) is None")

def test_datetimedelta_datetimedelta2(config_data):
	check_vsql(config_data, "(app.p_datetimedelta_value.value and hours(12)) == hours(12)")

def test_intlist_intlist1(config_data):
	check_vsql(config_data, "(0*[1] and [4, 5, 6]) == 0*[1]")

def test_intlist_intlist2(config_data):
	check_vsql(config_data, "([1, 2, 3] and [4, 5, 6]) == [4, 5, 6]")

def test_numberlist_numberlist1(config_data):
	check_vsql(config_data, "(0*[1.1] and [4.4, 5.5, 6.6]) == 0*[1.1]")

def test_numberlist_numberlist2(config_data):
	check_vsql(config_data, "([1.1, 2.2, 3.3] and [4.4, 5.5, 6.6]) == [4.4, 5.5, 6.6]")

def test_nulllist_intlist1(config_data):
	check_vsql(config_data, "([] and [4, 5, 6]) == []")

def test_nulllist_intlist2(config_data):
	check_vsql(config_data, "([None] and [4, 5, 6]) == [4, 5, 6]")

def test_nulllist_numberlist1(config_data):
	check_vsql(config_data, "([] and [4.4, 5.5, 6.6]) == []")

def test_nulllist_numberlist2(config_data):
	check_vsql(config_data, "([None] and [4.4, 5.5, 6.6]) == [4.4, 5.5, 6.6]")

def test_nulllist_strlist1(config_data):
	check_vsql(config_data, "([] and ['gurk', 'hurz']) == []")

def test_nulllist_strlist2(config_data):
	check_vsql(config_data, "([None] and ['gurk', 'hurz']) == ['gurk', 'hurz']")

def test_nulllist_datelist1(config_data):
	check_vsql(config_data, f"([] and [{d1}, {d2}]) == []")

def test_nulllist_datelist2(config_data):
	check_vsql(config_data, f"([None] and [{d1}, {d2}]) == [{d1}, {d2}]")

def test_nulllist_datetimelist1(config_data):
	check_vsql(config_data, f"([] and [{dt1}, {dt2}]) == []")

def test_nulllist_datetimelist2(config_data):
	check_vsql(config_data, f"([None] and [{dt1}, {dt2}]) == [{dt1}, {dt2}]")

def test_intlist_nulllist1(config_data):
	check_vsql(config_data, "([1, 2, 3] and []) == []")

def test_intlist_nulllist2(config_data):
	check_vsql(config_data, "([1, 2, 3] and [None]) == [None]")

def test_numberlist_nulllist1(config_data):
	check_vsql(config_data, "([1.1, 2.2, 3.3] and []) == []")

def test_numberlist_nulllist2(config_data):
	check_vsql(config_data, "([1.1, 2.2, 3.3] and [None]) == [None]")

def test_strlist_nulllist1(config_data):
	check_vsql(config_data, "(['gurk', 'hurz'] and []) == []")

def test_strlist_nulllist2(config_data):
	check_vsql(config_data, "(['gurk', 'hurz'] and [None]) == [None]")

def test_datelist_nulllist1(config_data):
	check_vsql(config_data, f"([{d1}, {d2}] and []) == []")

def test_datelist_nulllist2(config_data):
	check_vsql(config_data, f"([{d1}, {d2}] and [None]) == [None]")

def test_datetimelist_nulllist1(config_data):
	check_vsql(config_data, f"([{dt1}, {dt2}] and []) == []")

def test_datetimelist_nulllist2(config_data):
	check_vsql(config_data, f"([{dt1}, {dt2}] and [None]) == [None]")
