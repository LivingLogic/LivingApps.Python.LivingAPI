"""
Tests for the vSQL binary operator ``or``.

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
	check_vsql(config_data, "(None or app.p_bool_true.value) == app.p_bool_true.value")

def test_bool_null(config_data):
	check_vsql(config_data, "(app.p_bool_true.value or None) == app.p_bool_true.value")

def test_bool_bool1(config_data):
	check_vsql(config_data, "(app.p_bool_false.value or app.p_bool_false.value) == False")

def test_bool_bool2(config_data):
	check_vsql(config_data, "(app.p_bool_true.value or app.p_bool_false.value) == True")

def test_int_int1(config_data):
	check_vsql(config_data, "(0 or app.p_int_value.value) == app.p_int_value.value")

def test_int_int2(config_data):
	check_vsql(config_data, "(42 or app.p_int_value.value) == 42")

def test_number_number1(config_data):
	check_vsql(config_data, "(0.0 or app.p_number_value.value) == app.p_number_value.value")

def test_number_number2(config_data):
	check_vsql(config_data, "(42.5 or app.p_number_value.value) == 42.5")

def test_str_str1(config_data):
	check_vsql(config_data, "('' or app.p_str_value.value) == app.p_str_value.value")

def test_str_str2(config_data):
	check_vsql(config_data, "('hurz' or app.p_str_value.value) == 'hurz'")

def test_date_date1(config_data):
	check_vsql(config_data, f"({d1} or app.p_date_none.value) == {d1}")

def test_date_date2(config_data):
	check_vsql(config_data, f"({d1} or app.p_date_value.value) == {d1}")

def test_datetime_datetime1(config_data):
	check_vsql(config_data, f"(app.p_datetime_none.value or {dt1}) == {dt1}")

def test_datetime_datetime2(config_data):
	check_vsql(config_data, f"(app.p_datetime_value.value or {dt1}) == app.p_datetime_value.value")

def test_datedelta_datedelta1(config_data):
	check_vsql(config_data, "(app.p_datedelta_none.value or days(10)) == days(10)")

def test_datedelta_datedelta2(config_data):
	check_vsql(config_data, "(app.p_datedelta_value.value or days(10)) == app.p_datedelta_value.value")

def test_datetimedelta_datetimedelta1(config_data):
	check_vsql(config_data, "(app.p_datetimedelta_none.value or hours(12)) == hours(12)")

def test_datetimedelta_datetimedelta2(config_data):
	check_vsql(config_data, "(app.p_datetimedelta_value.value or hours(12)) == app.p_datetimedelta_value.value")

def test_intlist_intlist1(config_data):
	check_vsql(config_data, "(0*[1] or [4, 5, 6]) == [4, 5, 6]")

def test_intlist_intlist2(config_data):
	check_vsql(config_data, "([1, 2, 3] or [4, 5, 6]) == [1, 2, 3]")

def test_numberlist_numberlist1(config_data):
	check_vsql(config_data, "(0*[1.1] or [4.4, 5.5, 6.6]) == [4.4, 5.5, 6.6]")

def test_numberlist_numberlist2(config_data):
	check_vsql(config_data, "([1.1, 2.2, 3.3] or [4.4, 5.5, 6.6]) == [1.1, 2.2, 3.3]")

def test_nulllist_intlist1(config_data):
	check_vsql(config_data, "([] or [4, 5, 6]) == [4, 5, 6]")

def test_nulllist_intlist2(config_data):
	check_vsql(config_data, "([None] or [4, 5, 6]) == [None]")

def test_nulllist_numberlist1(config_data):
	check_vsql(config_data, "([] or [4.4, 5.5, 6.6]) == [4.4, 5.5, 6.6]")

def test_nulllist_numberlist2(config_data):
	check_vsql(config_data, "([None] or [4.4, 5.5, 6.6]) == [None]")

def test_nulllist_strlist1(config_data):
	check_vsql(config_data, "([] or ['gurk', 'hurz']) == ['gurk', 'hurz']")

def test_nulllist_strlist2(config_data):
	check_vsql(config_data, "([None] or ['gurk', 'hurz']) == [None]")

def test_nulllist_datelist1(config_data):
	check_vsql(config_data, f"([] or [{d1}, {d2}]) == [{d1}, {d2}]")

def test_nulllist_datelist2(config_data):
	check_vsql(config_data, f"([None] or [{d1}, {d2}]) == [None]")

def test_nulllist_datetimelist1(config_data):
	check_vsql(config_data, f"([] or [{dt1}, {dt2}]) == [{dt1}, {dt2}]")

def test_nulllist_datetimelist2(config_data):
	check_vsql(config_data, f"([None] or [{dt1}, {dt2}]) == [None]")

def test_intlist_nulllist1(config_data):
	check_vsql(config_data, "([1, 2, 3] or []) == [1, 2, 3]")

def test_intlist_nulllist2(config_data):
	check_vsql(config_data, "([1, 2, 3] or [None]) == [1, 2, 3]")

def test_numberlist_nulllist1(config_data):
	check_vsql(config_data, "([1.1, 2.2, 3.3] or []) == [1.1, 2.2, 3.3]")

def test_numberlist_nulllist2(config_data):
	check_vsql(config_data, "([1.1, 2.2, 3.3] or [None]) == [1.1, 2.2, 3.3]")

def test_strlist_nulllist1(config_data):
	check_vsql(config_data, "(['gurk', 'hurz'] or []) == ['gurk', 'hurz']")

def test_strlist_nulllist2(config_data):
	check_vsql(config_data, "(['gurk', 'hurz'] or [None]) == ['gurk', 'hurz']")

def test_datelist_nulllist1(config_data):
	check_vsql(config_data, f"([{d1}, {d2}] or []) == [{d1}, {d2}]")

def test_datelist_nulllist2(config_data):
	check_vsql(config_data, f"([{d1}, {d2}] or [None]) == [{d1}, {d2}]")

def test_datetimelist_nulllist1(config_data):
	check_vsql(config_data, f"([{dt1}, {dt2}] or []) == [{dt1}, {dt2}]")

def test_datetimelist_nulllist2(config_data):
	check_vsql(config_data, f"([{dt1}, {dt2}] or [None]) == [{dt1}, {dt2}]")
