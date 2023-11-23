"""
Tests for the vSQL multiplication operator ``*``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_int_none.value * True is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value * True == 0")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value * True == 1")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value * 1 == 1")

def test_bool_number(config_data):
	check_vsql(config_data, "app.p_bool_true.value * 1.5 == 1.5")

def test_int_bool(config_data):
	check_vsql(config_data, "2 * app.p_bool_true.value == 2")

def test_int_int(config_data):
	check_vsql(config_data, "2 *  app.p_int_value.value == 3554")

def test_int_number(config_data):
	check_vsql(config_data, "2 * app.p_number_value.value == 85.0")

def test_number_bool(config_data):
	check_vsql(config_data, "app.p_number_value.value * app.p_bool_true.value == 42.5")

def test_number_int(config_data):
	check_vsql(config_data, "app.p_number_value.value * 2 == 85.0")

def test_number_number(config_data):
	check_vsql(config_data, "app.p_number_value.value * 1.5 == 63.75")

def test_bool_str1(config_data):
	check_vsql(config_data, "app.p_bool_none.value * app.p_str_none.value == ''")

def test_bool_str2(config_data):
	check_vsql(config_data, "app.p_bool_false.value * app.p_str_none.value == ''")

def test_bool_str3(config_data):
	check_vsql(config_data, "app.p_bool_true.value * app.p_str_none.value == ''")

def test_bool_str4(config_data):
	check_vsql(config_data, "app.p_bool_none.value * app.p_str_value.value == ''")

def test_bool_str5(config_data):
	check_vsql(config_data, "app.p_bool_false.value * app.p_str_value.value == ''")

def test_bool_str6(config_data):
	check_vsql(config_data, "app.p_bool_true.value * app.p_str_value.value == 'gurk'")

def test_int_str1(config_data):
	check_vsql(config_data, "app.p_int_none.value * app.p_str_none.value == ''")

def test_int_str2(config_data):
	check_vsql(config_data, "2 * app.p_str_none.value == ''")

def test_int_str3(config_data):
	check_vsql(config_data, "app.p_int_none.value * app.p_str_value.value == ''")

def test_int_str4(config_data):
	check_vsql(config_data, "2 * app.p_str_value.value == 'gurkgurk'")

def test_bool_datedelta1(config_data):
	check_vsql(config_data, "app.p_bool_none.value * days(3) is None")

def test_bool_datedelta2(config_data):
	check_vsql(config_data, "True * app.p_datedelta_none.value is None")

def test_bool_datedelta3(config_data):
	check_vsql(config_data, "True * app.p_datedelta_value.value == days(12)")

def test_int_datedelta1(config_data):
	check_vsql(config_data, "app.p_int_none.value * days(3) is None")

def test_int_datedelta2(config_data):
	check_vsql(config_data, "2 * app.p_datedelta_none.value is None")

def test_int_datedelta3(config_data):
	check_vsql(config_data, "2 * app.p_datedelta_value.value == days(24)")

def test_bool_datetimedelta1(config_data):
	check_vsql(config_data, "app.p_bool_none.value * minutes(3) is None")

def test_bool_datetimedelta2(config_data):
	check_vsql(config_data, "True * app.p_datetimedelta_none.value is None")

def test_bool_datetimedelta3(config_data):
	check_vsql(config_data, "True * app.p_datetimedelta_value.value == timedelta(1, (12 * 60 + 34) * 60 + 56)")

def test_int_datetimedelta1(config_data):
	check_vsql(config_data, "app.p_int_none.value * minutes(3) is None")

def test_int_datetimedelta2(config_data):
	check_vsql(config_data, "2 * app.p_datetimedelta_none.value is None")

def test_int_datetimedelta3(config_data):
	check_vsql(config_data, "2 * app.p_datetimedelta_value.value == timedelta(3, (1 * 60 + 9) * 60 + 52)")

def test_bool_monthdelta1(config_data):
	check_vsql(config_data, "app.p_bool_none.value * months(3) is None")

def test_bool_monthdelta2(config_data):
	check_vsql(config_data, "True * app.p_monthdelta_none.value is None")

def test_bool_monthdelta3(config_data):
	check_vsql(config_data, "True * app.p_monthdelta_value.value == months(3)")

def test_int_monthdelta1(config_data):
	check_vsql(config_data, "app.p_int_none.value * months(3) is None")

def test_int_monthdelta2(config_data):
	check_vsql(config_data, "2 * app.p_monthdelta_none.value is None")

def test_int_monthdelta3(config_data):
	check_vsql(config_data, "2 * app.p_monthdelta_value.value == months(6)")

def test_number_datetimedelta3(config_data):
	check_vsql(config_data, "2.5 * app.p_datetimedelta_value.value == timedelta(3, (19 * 60 + 27) * 60 + 20)")

def test_str_bool1(config_data):
	check_vsql(config_data, "app.p_str_none.value * app.p_bool_none.value == ''")

def test_str_bool2(config_data):
	check_vsql(config_data, "app.p_str_none.value * app.p_bool_false.value == ''")

def test_str_bool3(config_data):
	check_vsql(config_data, "app.p_str_none.value * app.p_bool_true.value == ''")

def test_str_bool4(config_data):
	check_vsql(config_data, "app.p_str_value.value * app.p_bool_none.value == ''")

def test_str_bool5(config_data):
	check_vsql(config_data, "app.p_str_value.value * app.p_bool_false.value == ''")

def test_str_bool6(config_data):
	check_vsql(config_data, "app.p_str_value.value * app.p_bool_true.value == 'gurk'")

def test_str_int1(config_data):
	check_vsql(config_data, "app.p_str_none.value * app.p_int_none.value == ''")

def test_str_int2(config_data):
	check_vsql(config_data, "app.p_str_none.value * 2 == ''")

def test_str_int3(config_data):
	check_vsql(config_data, "app.p_str_value.value * app.p_int_none.value == ''")

def test_bool_intlist1(config_data):
	check_vsql(config_data, "app.p_bool_none.value * [1, 2, 3] is None")

def test_bool_intlist2(config_data):
	check_vsql(config_data, "app.p_bool_false.value * [1, 2, 3] == [1][:0]")

def test_int_intlist1(config_data):
	check_vsql(config_data, "app.p_int_none.value * [1, 2, 3] is None")

def test_int_intlist2(config_data):
	check_vsql(config_data, "2 * [1, 2, 3] == [1, 2, 3, 1, 2, 3]")

def test_bool_nulllist1(config_data):
	check_vsql(config_data, "False * [] == []")

def test_bool_nulllist2(config_data):
	check_vsql(config_data, "True * [] == []")

def test_bool_nulllist3(config_data):
	check_vsql(config_data, "False * [None, None] == []")

def test_bool_nulllist4(config_data):
	check_vsql(config_data, "True * [None, None] == [None, None]")

def test_int_nulllist1(config_data):
	check_vsql(config_data, "0 * [] == []")

def test_int_nulllist2(config_data):
	check_vsql(config_data, "2 * [] == []")

def test_int_nulllist3(config_data):
	check_vsql(config_data, "0 * [None, None] == []")

def test_int_nulllist4(config_data):
	check_vsql(config_data, "2 * [None, None] == [None, None, None, None]")

def test_nulllist1_bool(config_data):
	check_vsql(config_data, "[] * False == []")

def test_nulllist2_bool(config_data):
	check_vsql(config_data, "[] * True == []")

def test_nulllist3_bool(config_data):
	check_vsql(config_data, "[None, None] * False == []")

def test_nulllist4_bool(config_data):
	check_vsql(config_data, "[None, None] * True == [None, None]")

def test_nulllist1_int(config_data):
	check_vsql(config_data, "[] * 0 == []")

def test_nulllist2_int(config_data):
	check_vsql(config_data, "[] * 2 == []")

def test_nulllist3_int(config_data):
	check_vsql(config_data, "[None, None] * 0 == []")

def test_nulllist4_int(config_data):
	check_vsql(config_data, "[None, None] * 2 == [None, None, None, None]")
