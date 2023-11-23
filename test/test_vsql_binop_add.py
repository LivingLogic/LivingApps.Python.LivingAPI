"""
Tests for the vSQL addition operator ``+``.

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

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_bool_none.value + True is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value + True == 1")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value + True == 2")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value + 1 == 2")

def test_bool_number(config_data):
	check_vsql(config_data, "app.p_bool_true.value + 1.5 == 2.5")

def test_int_bool(config_data):
	check_vsql(config_data, "1 + app.p_bool_true.value == 2")

def test_int_int(config_data):
	check_vsql(config_data, "1 + app.p_int_value.value == 1778")

def test_int_number(config_data):
	check_vsql(config_data, "1 + app.p_number_value.value == 43.5")

def test_str_str1(config_data):
	check_vsql(config_data, "'gurk' + app.p_str_none.value == 'gurk'")

def test_str_str2(config_data):
	check_vsql(config_data, "'gurk' + app.p_str_value.value == 'gurkgurk'")

def test_intlist_intlist(config_data):
	check_vsql(config_data, "[1, 2] + [3, 4] == [1, 2, 3, 4]")

def test_intlist_numberlist(config_data):
	check_vsql(config_data, "[1, 2] + [3.5, 4.5] == [1.0, 2.0, 3.5, 4.5]")

def test_numberlist_intlist(config_data):
	check_vsql(config_data, "[1.5, 2.5] + [3, 4] == [1.5, 2.5, 3.0, 4.0]")

def test_numberlist_numberlist(config_data):
	check_vsql(config_data, "[1.5, 2.5] + [3.5, 4.5] == [1.5, 2.5, 3.5, 4.5]")

def test_strlist_strlist(config_data):
	check_vsql(config_data, "['gurk', 'hurz'] + ['hinz', 'kunz'] == ['gurk', 'hurz', 'hinz', 'kunz']")

def test_datelist_datelist(config_data):
	check_vsql(config_data, "[@(2000-02-29), @(2000-03-01)] + [@(2000-03-02), @(2000-03-03)] == [@(2000-02-29), @(2000-03-01), @(2000-03-02), @(2000-03-03)]")

def test_datetimelist_datetimelist(config_data):
	check_vsql(config_data, "[@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)] + [@(2000-03-02T12:34:56), @(2000-03-03T12:34:56)] == [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56), @(2000-03-02T12:34:56), @(2000-03-03T12:34:56)]")

def test_date_datedelta(config_data):
	check_vsql(config_data, "app.p_date_value.value + days(1) == @(2000-03-01)")

def test_date_monthdelta(config_data):
	check_vsql(config_data, "@(2000-01-31) + months(1) == app.p_date_value.value")

def test_datetime_datedelta(config_data):
	check_vsql(config_data, "app.p_datetime_value.value + days(1) == @(2000-03-01T12:34:56)")

def test_datetime_datetimedelta(config_data):
	check_vsql(config_data, "app.p_datetime_value.value + timedelta(1, 1) == @(2000-03-01T12:34:57)")

def test_datetime_monthdelta(config_data):
	check_vsql(config_data, "@(2000-01-31T12:34:56) + months(1) == app.p_datetime_value.value")

def test_monthdelta_date(config_data):
	check_vsql(config_data, "months(1) + @(2000-01-31) == app.p_date_value.value")

def test_monthdelta_datetime(config_data):
	check_vsql(config_data, "months(1) + @(2000-01-31T12:34:56) == app.p_datetime_value.value")

def test_datedelta_datedelta(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value + days(12) == days(24)")

def test_datedelta_datetimedelta(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value + timedelta(1, 1) == timedelta(13, 1)")

def test_datetimedelta_datedelta(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value + days(12) == timedelta(13, (12 * 60 + 34) * 60 + 56)")

def test_datetimedelta_datetimedelta(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value + timedelta(2, (12 * 60 + 34) * 60 + 56) == timedelta(4, (1 * 60 + 9) * 60 + 52)")

def test_monthdelta_monthdelta(config_data):
	check_vsql(config_data, "app.p_monthdelta_value.value + months(9) == months(12)")

def test_nulllist_nulllist1(config_data):
	check_vsql(config_data, "[] + [] == []")

def test_nulllist_nulllist2(config_data):
	check_vsql(config_data, "[None, None] + [None] == [None, None, None]")

def test_nulllist_intlist1(config_data):
	check_vsql(config_data, "[] + [1, None, 2] == [1, None, 2]")

def test_nulllist_intlist2(config_data):
	check_vsql(config_data, "[None, None] + [1, None, 2] == [None, None, 1, None, 2]")

def test_nulllist_numberlist1(config_data):
	check_vsql(config_data, "[] + [1.1, None, 2.2] == [1.1, None, 2.2]")

def test_nulllist_numberlist2(config_data):
	check_vsql(config_data, "[None, None] + [1.1, None, 2.2] == [None, None, 1.1, None, 2.2]")

def test_nulllist_strlist1(config_data):
	check_vsql(config_data, "[] + ['gurk', None, 'hurz'] == ['gurk', None, 'hurz']")

def test_nulllist_strlist2(config_data):
	check_vsql(config_data, "[None, None] + ['gurk', None, 'hurz'] == [None, None, 'gurk', None, 'hurz']")

def test_nulllist_datelist1(config_data):
	check_vsql(config_data, f"[] + [{d1}, None, {d2}] == [{d1}, None, {d2}]")

def test_nulllist_datelist2(config_data):
	check_vsql(config_data, f"[None, None] + [{d1}, None, {d2}] == [None, None, {d1}, None, {d2}]")

def test_nulllist_datetimelist1(config_data):
	check_vsql(config_data, f"[] + [{dt1}, None, {dt2}] == [{dt1}, None, {dt2}]")

def test_nulllist_datetimelist2(config_data):
	check_vsql(config_data, f"[None, None] + [{dt1}, None, {dt2}] == [None, None, {dt1}, None, {dt2}]")

def test_intlist_nulllist1(config_data):
	check_vsql(config_data, "[1, None, 2] + [] == [1, None, 2]")

def test_intlist_nulllist2(config_data):
	check_vsql(config_data, "[1, None, 2] + [None, None] == [1, None, 2, None, None]")

def test_numberlist_nulllist1(config_data):
	check_vsql(config_data, "[1.1, None, 2.2] + [] == [1.1, None, 2.2]")

def test_numberlist_nulllist2(config_data):
	check_vsql(config_data, "[1.1, None, 2.2] + [None, None] == [1.1, None, 2.2, None, None]")

def test_strlist_nulllist1(config_data):
	check_vsql(config_data, "['gurk', None, 'hurz'] + [] == ['gurk', None, 'hurz']")

def test_strlist_nulllist2(config_data):
	check_vsql(config_data, "['gurk', None, 'hurz'] + [None, None] == ['gurk', None, 'hurz', None, None]")

def test_datelist_nulllist1(config_data):
	check_vsql(config_data, f"[{d1}, None, {d2}] + [] == [{d1}, None, {d2}]")

def test_datelist_nulllist2(config_data):
	check_vsql(config_data, f"[{d1}, None, {d2}] + [None, None] == [{d1}, None, {d2}, None, None]")

def test_datetimelist_nulllist1(config_data):
	check_vsql(config_data, f"[{dt1}, None, {dt2}] + [] == [{dt1}, None, {dt2}]")

def test_datetimelist_nulllist2(config_data):
	check_vsql(config_data, f"[{dt1}, None, {dt2}] + [None, None] == [{dt1}, None, {dt2}, None, None]")
