"""
Tests for the vSQL binary identity test operator ``is``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool1(config_persons):
	check_vsql(config_persons, "app.p_bool_none.value is None")

def test_bool2(config_persons):
	check_vsql(config_persons, "not (app.p_bool_false.value is None)")

def test_bool3(config_persons):
	check_vsql(config_persons, "not (app.p_bool_true.value is None)")

def test_bool4(config_persons):
	check_vsql(config_persons, "None is app.p_bool_none.value")

def test_bool5(config_persons):
	check_vsql(config_persons, "not (None is app.p_bool_false.value)")

def test_bool6(config_persons):
	check_vsql(config_persons, "not (None is app.p_bool_true.value)")

def test_int1(config_persons):
	check_vsql(config_persons, "app.p_int_none.value is None")

def test_int2(config_persons):
	check_vsql(config_persons, "not (app.p_int_value.value is None)")

def test_int3(config_persons):
	check_vsql(config_persons, "None is app.p_int_none.value")

def test_int4(config_persons):
	check_vsql(config_persons, "not (None is app.p_int_value.value)")

def test_number1(config_persons):
	check_vsql(config_persons, "app.p_number_none.value is None")

def test_number2(config_persons):
	check_vsql(config_persons, "not (app.p_number_value.value is None)")

def test_number3(config_persons):
	check_vsql(config_persons, "None is app.p_number_none.value")

def test_number4(config_persons):
	check_vsql(config_persons, "not (None is app.p_number_value.value)")

def test_str1(config_persons):
	check_vsql(config_persons, "app.p_str_none.value is None")

def test_str2(config_persons):
	check_vsql(config_persons, "not (app.p_str_value.value is None)")

def test_str3(config_persons):
	check_vsql(config_persons, "None is app.p_str_none.value")

def test_str4(config_persons):
	check_vsql(config_persons, "not (None is app.p_str_value.value)")

def test_color1(config_persons):
	check_vsql(config_persons, "app.p_color_none.value is None")

def test_color2(config_persons):
	check_vsql(config_persons, "not (app.p_color_value.value is None)")

def test_color3(config_persons):
	check_vsql(config_persons, "None is app.p_color_none.value")

def test_color4(config_persons):
	check_vsql(config_persons, "not (None is app.p_color_value.value)")

def test_date1(config_persons):
	check_vsql(config_persons, "app.p_date_none.value is None")

def test_date2(config_persons):
	check_vsql(config_persons, "not (app.p_date_value.value is None)")

def test_date3(config_persons):
	check_vsql(config_persons, "None is app.p_date_none.value")

def test_date4(config_persons):
	check_vsql(config_persons, "not (None is app.p_date_value.value)")

def test_datetime1(config_persons):
	check_vsql(config_persons, "app.p_datetime_none.value is None")

def test_datetime2(config_persons):
	check_vsql(config_persons, "not (app.p_datetime_value.value is None)")

def test_datetime3(config_persons):
	check_vsql(config_persons, "None is app.p_datetime_none.value")

def test_datetime4(config_persons):
	check_vsql(config_persons, "not (None is app.p_datetime_value.value)")

def test_datedelta1(config_persons):
	check_vsql(config_persons, "app.p_datedelta_none.value is None")

def test_datedelta2(config_persons):
	check_vsql(config_persons, "not (app.p_datedelta_value.value is None)")

def test_datedelta3(config_persons):
	check_vsql(config_persons, "None is app.p_datedelta_none.value")

def test_datedelta4(config_persons):
	check_vsql(config_persons, "not (None is app.p_datedelta_value.value)")

def test_datetimedelta1(config_persons):
	check_vsql(config_persons, "app.p_datetimedelta_none.value is None")

def test_datetimedelta2(config_persons):
	check_vsql(config_persons, "not (app.p_datetimedelta_value.value is None)")

def test_datetimedelta3(config_persons):
	check_vsql(config_persons, "None is app.p_datetimedelta_none.value")

def test_datetimedelta4(config_persons):
	check_vsql(config_persons, "not (None is app.p_datetimedelta_value.value)")

def test_monthdelta1(config_persons):
	check_vsql(config_persons, "app.p_monthdelta_none.value is None")

def test_monthdelta2(config_persons):
	check_vsql(config_persons, "not (app.p_monthdelta_value.value is None)")

def test_monthdelta3(config_persons):
	check_vsql(config_persons, "None is app.p_monthdelta_none.value")

def test_monthdelta4(config_persons):
	check_vsql(config_persons, "not (None is app.p_monthdelta_value.value)")

def test_geo1(config_persons):
	check_vsql(config_persons, "not (geo(49, 11, 'Here') is None)")

def test_geo2(config_persons):
	check_vsql(config_persons, "not (None is geo(49, 11, 'Here'))")

def test_intlist1(config_persons):
	check_vsql(config_persons, "not ([1, 2, 3] is None)")

def test_intlist2(config_persons):
	check_vsql(config_persons, "not (None is [1, 2, 3])")

def test_numberlist1(config_persons):
	check_vsql(config_persons, "not ([1.1, 2.2, 3.3] is None)")

def test_numberlist2(config_persons):
	check_vsql(config_persons, "not (None is [1.1, 2.2, 3.3])")

def test_strlist1(config_persons):
	check_vsql(config_persons, "not (['gurk', 'hurz'] is None)")

def test_strlist2(config_persons):
	check_vsql(config_persons, "not (None is ['gurk', 'hurz'])")

def test_datelist1(config_persons):
	check_vsql(config_persons, "not ([@(2000-02-29), @(2000-03-01)] is None)")

def test_datelist2(config_persons):
	check_vsql(config_persons, "not (None is [@(2000-02-29), @(2000-03-01)])")

def test_datetimelist1(config_persons):
	check_vsql(config_persons, "not ([@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)] is None)")

def test_datetimelist2(config_persons):
	check_vsql(config_persons, "not (None is [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)])")
