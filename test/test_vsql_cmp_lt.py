"""
Tests for the vSQL "less than" comparison operator ``<``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_none1(config_data):
	check_vsql(config_data, "not (app.p_bool_none.value < None)")

def test_bool_none2(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < None)")

def test_bool_none3(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < None)")

def test_int_none1(config_data):
	check_vsql(config_data, "not (app.p_int_none.value < None)")

def test_int_none2(config_data):
	check_vsql(config_data, "not (app.p_int_value.value < None)")

def test_number_none1(config_data):
	check_vsql(config_data, "not (app.p_number_none.value < None)")

def test_number_none2(config_data):
	check_vsql(config_data, "not (app.p_number_value.value < None)")

def test_str_none1(config_data):
	check_vsql(config_data, "not (app.p_str_none.value < None)")

def test_str_none2(config_data):
	check_vsql(config_data, "not (app.p_str_value.value < None)")

def test_date_none1(config_data):
	check_vsql(config_data, "not (app.p_date_none.value < None)")

def test_date_none2(config_data):
	check_vsql(config_data, "not (app.p_date_value.value < None)")

def test_datetime_none1(config_data):
	check_vsql(config_data, "not (app.p_datetime_none.value < None)")

def test_datetime_none2(config_data):
	check_vsql(config_data, "not (app.p_datetime_value.value < None)")

def test_color_none1(config_data):
	check_vsql(config_data, "not (app.p_color_none.value < None)")

def test_color_none2(config_data):
	check_vsql(config_data, "not (app.p_color_value.value < None)")

def test_datedelta_none1(config_data):
	check_vsql(config_data, "not (app.p_datedelta_none.value < None)")

def test_datedelta_none2(config_data):
	check_vsql(config_data, "not (app.p_datedelta_value.value < None)")

def test_datetimedelta_none1(config_data):
	check_vsql(config_data, "not (app.p_datetimedelta_none.value < None)")

def test_datetimedelta_none2(config_data):
	check_vsql(config_data, "not (app.p_datetimedelta_value.value < None)")

def test_monthdelta_none1(config_data):
	check_vsql(config_data, "not (app.p_monthdelta_none.value < None)")

def test_monthdelta_none2(config_data):
	check_vsql(config_data, "not (app.p_monthdelta_value.value < None)")

def test_intlist_none(config_data):
	check_vsql(config_data, "not ([1, 2] < None)")

def test_numberlist_none(config_data):
	check_vsql(config_data, "not ([1.2, 3.4] < None)")

def test_strlist_none(config_data):
	check_vsql(config_data, "not (['foo', 'bar'] < None)")

def test_datelist_none(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] < None)")

def test_datetimelist_none(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] < None)")

def test_none_bool1(config_data):
	check_vsql(config_data, "not (None < app.p_bool_none.value)")

def test_none_bool2(config_data):
	check_vsql(config_data, "None < app.p_bool_false.value")

def test_none_bool3(config_data):
	check_vsql(config_data, "None < app.p_bool_true.value")

def test_none_int1(config_data):
	check_vsql(config_data, "not (None < app.p_int_none.value)")

def test_none_int2(config_data):
	check_vsql(config_data, "None < app.p_int_value.value")

def test_none_number1(config_data):
	check_vsql(config_data, "not (None < app.p_number_none.value)")

def test_none_number2(config_data):
	check_vsql(config_data, "None < app.p_number_value.value")

def test_none_str1(config_data):
	check_vsql(config_data, "not (None < app.p_str_none.value)")

def test_none_str2(config_data):
	check_vsql(config_data, "None < app.p_str_value.value")

def test_none_date1(config_data):
	check_vsql(config_data, "not (None < app.p_date_none.value)")

def test_none_date2(config_data):
	check_vsql(config_data, "None < app.p_date_value.value")

def test_none_datetime1(config_data):
	check_vsql(config_data, "not (None < app.p_datetime_none.value)")

def test_none_datetime2(config_data):
	check_vsql(config_data, "None < app.p_datetime_value.value")

def test_none_color1(config_data):
	check_vsql(config_data, "not (None < app.p_color_none.value)")

def test_none_color2(config_data):
	check_vsql(config_data, "None < app.p_color_value.value")

def test_none_datedelta1(config_data):
	check_vsql(config_data, "not (None < app.p_datedelta_none.value)")

def test_none_datedelta2(config_data):
	check_vsql(config_data, "None < app.p_datedelta_value.value")

def test_none_datetimedelta1(config_data):
	check_vsql(config_data, "not (None < app.p_datetimedelta_none.value)")

def test_none_datetimedelta2(config_data):
	check_vsql(config_data, "None < app.p_datetimedelta_value.value")

def test_none_monthdelta1(config_data):
	check_vsql(config_data, "not (None < app.p_monthdelta_none.value)")

def test_none_monthdelta2(config_data):
	check_vsql(config_data, "None < app.p_monthdelta_value.value")

def test_none_intlist(config_data):
	check_vsql(config_data, "None < [1, 2]")

def test_none_numberlist(config_data):
	check_vsql(config_data, "None < [1.2, 3.4]")

def test_none_strlist(config_data):
	check_vsql(config_data, "None < ['foo', 'bar']")

def test_none_datelist(config_data):
	check_vsql(config_data, "None < [@(2000-02-29)]")

def test_none_datetimelist(config_data):
	check_vsql(config_data, "None < [@(2000-02-29T12:34:56)]")

def test_bool_bool1(config_data):
	check_vsql(config_data, "not (app.p_bool_none.value < app.p_bool_none.value)")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_none.value < app.p_bool_false.value")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_none.value < app.p_bool_true.value")

def test_bool_bool4(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < app.p_bool_none.value)")

def test_bool_bool5(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < app.p_bool_false.value)")

def test_bool_bool6(config_data):
	check_vsql(config_data, "app.p_bool_false.value < app.p_bool_true.value")

def test_bool_bool7(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < app.p_bool_none.value)")

def test_bool_bool8(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < app.p_bool_false.value)")

def test_bool_bool9(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < app.p_bool_true.value)")

def test_bool_int1(config_data):
	check_vsql(config_data, "not (app.p_bool_none.value < app.p_int_none.value)")

def test_bool_int2(config_data):
	check_vsql(config_data, "app.p_bool_none.value < -1")

def test_bool_int3(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < app.p_int_none.value)")

def test_bool_int4(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < 0)")

def test_bool_int5(config_data):
	check_vsql(config_data, "app.p_bool_false.value < 1")

def test_bool_int6(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < app.p_int_none.value)")

def test_bool_int7(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < 1)")

def test_bool_int8(config_data):
	check_vsql(config_data, "app.p_bool_true.value < 2")

def test_bool_number1(config_data):
	check_vsql(config_data, "not (app.p_bool_none.value < app.p_number_none.value)")

def test_bool_number2(config_data):
	check_vsql(config_data, "app.p_bool_none.value < -1.0")

def test_bool_number3(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < app.p_number_none.value)")

def test_bool_number4(config_data):
	check_vsql(config_data, "not (app.p_bool_false.value < 0.0)")

def test_bool_number5(config_data):
	check_vsql(config_data, "app.p_bool_false.value < 1.0")

def test_bool_number6(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < app.p_number_none.value)")

def test_bool_number7(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value < 1.0)")

def test_bool_number8(config_data):
	check_vsql(config_data, "app.p_bool_true.value < 2.0")

def test_int_bool1(config_data):
	check_vsql(config_data, "not (app.p_int_none.value < app.p_bool_none.value)")

def test_int_bool2(config_data):
	check_vsql(config_data, "app.p_int_none.value < app.p_bool_false.value")

def test_int_bool3(config_data):
	check_vsql(config_data, "app.p_int_none.value < app.p_bool_true.value")

def test_int_bool4(config_data):
	check_vsql(config_data, "not (app.p_int_value.value < app.p_bool_none.value)")

def test_int_bool5(config_data):
	check_vsql(config_data, "not (app.p_int_value.value < app.p_bool_false.value)")

def test_int_bool6(config_data):
	check_vsql(config_data, "not (app.p_int_value.value < app.p_bool_true.value)")

def test_int_bool7(config_data):
	check_vsql(config_data, "not (-app.p_int_value.value < app.p_bool_none.value)")

def test_int_bool8(config_data):
	check_vsql(config_data, "-app.p_int_value.value < app.p_bool_false.value")

def test_int_bool9(config_data):
	check_vsql(config_data, "-app.p_int_value.value < app.p_bool_true.value")

def test_int_int1(config_data):
	check_vsql(config_data, "not (app.p_int_none.value < app.p_int_none.value)")

def test_int_int2(config_data):
	check_vsql(config_data, "app.p_int_none.value < 1")

def test_int_int3(config_data):
	check_vsql(config_data, "not (app.p_int_value.value < 1777)")

def test_int_int4(config_data):
	check_vsql(config_data, "app.p_int_value.value < 1778")

def test_int_int5(config_data):
	check_vsql(config_data, "not (42 < app.p_int_none.value)")

def test_number_bool1(config_data):
	check_vsql(config_data, "not (app.p_number_none.value < app.p_bool_none.value)")

def test_number_bool2(config_data):
	check_vsql(config_data, "app.p_number_none.value < False")

def test_number_bool3(config_data):
	check_vsql(config_data, "not (app.p_number_value.value < True)")

def test_number_bool4(config_data):
	check_vsql(config_data, "-app.p_number_value.value < True")

def test_number_int1(config_data):
	check_vsql(config_data, "not (app.p_number_none.value < app.p_int_none.value)")

def test_number_int2(config_data):
	check_vsql(config_data, "app.p_number_none.value < 1")

def test_number_int3(config_data):
	check_vsql(config_data, "not (app.p_number_value.value < 1)")

def test_number_int4(config_data):
	check_vsql(config_data, "app.p_number_value.value < 73")

def test_number_number1(config_data):
	check_vsql(config_data, "not (app.p_number_none.value < app.p_number_none.value)")

def test_number_number2(config_data):
	check_vsql(config_data, "app.p_number_none.value < 1.0")

def test_number_number3(config_data):
	check_vsql(config_data, "not (app.p_number_value.value < 1.0)")

def test_number_number4(config_data):
	check_vsql(config_data, "app.p_number_value.value < 73.0")

def test_str_str(config_data):
	check_vsql(config_data, "'abc' < app.p_str_value.value")

def test_date_date(config_data):
	check_vsql(config_data, "@(2000-02-28) < app.p_date_value.value")

def test_datetime_datetime(config_data):
	check_vsql(config_data, "@(2000-02-28T23:59:59) < app.p_datetime_value.value")

def test_datedelta_datedelta(config_data):
	check_vsql(config_data, "days(1) < days(2)")

def test_datetimedelta_datetimedelta(config_data):
	check_vsql(config_data, "hours(1) < hours(2)")

def test_intlist_intlist1(config_data):
	check_vsql(config_data, "[1] < [1, 2]")

def test_intlist_intlist2(config_data):
	check_vsql(config_data, "[1, 2] < [1, 3]")

def test_intlist_intlist3(config_data):
	check_vsql(config_data, "not ([1, 2] < [1])")

def test_intlist_intlist4(config_data):
	check_vsql(config_data, "not ([1, 2] < [1, 2])")

def test_numberlist_numberlist1(config_data):
	check_vsql(config_data, "[1.5] < [1.5, 2.5]")

def test_numberlist_numberlist2(config_data):
	check_vsql(config_data, "[1.5, 2.5] < [1.5, 3.5]")

def test_numberlist_numberlist3(config_data):
	check_vsql(config_data, "not ([1.5, 2.5] < [1.5])")

def test_numberlist_numberlist4(config_data):
	check_vsql(config_data, "not ([1.5, 2.5] < [1.5, 2.5])")

def test_strlist_strlist1(config_data):
	check_vsql(config_data, "['foo'] < ['foo', 'bar']")

def test_strlist_strlist2(config_data):
	check_vsql(config_data, "['foo', 'bar'] < ['foo', 'baz']")

def test_strlist_strlist3(config_data):
	check_vsql(config_data, "['foo'] < ['foo', 'bar']")

def test_strlist_strlist4(config_data):
	check_vsql(config_data, "not (['foo', 'bar'] < ['foo', 'bar'])")

def test_datelist_datelist1(config_data):
	check_vsql(config_data, "[@(2000-02-29)] < [@(2000-02-29), @(2000-03-01)]")

def test_datelist_datelist2(config_data):
	check_vsql(config_data, "[@(2000-02-29), @(2000-03-01)] < [@(2000-02-29), @(2000-03-02)]")

def test_datelist_datelist3(config_data):
	check_vsql(config_data, "[@(2000-02-29)] < [@(2000-02-29), @(2000-03-01)]")

def test_datelist_datelist4(config_data):
	check_vsql(config_data, "not ([@(2000-02-29), @(2000-03-01)] < [@(2000-02-29), @(2000-03-01)])")

def test_datetimelist_datetimelist1(config_data):
	check_vsql(config_data, "[@(2000-02-29T12:34:56)] < [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)]")

def test_datetimelist_datetimelist2(config_data):
	check_vsql(config_data, "[@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)] < [@(2000-02-29T12:34:56), @(2000-03-02T12:34:56)]")

def test_datetimelist_datetimelist3(config_data):
	check_vsql(config_data, "[@(2000-02-29T12:34:56)] < [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)]")

def test_datetimelist_datetimelist4(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)] < [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)])")

def test_nulllist_nulllist1(config_data):
	check_vsql(config_data, "not ([] < [])")

def test_nulllist_nulllist2(config_data):
	check_vsql(config_data, "not ([None, None] < [])")

def test_nulllist_nulllist3(config_data):
	check_vsql(config_data, "[] < [None, None]")

def test_nulllist_intlist1(config_data):
	check_vsql(config_data, "[] < [1]")

def test_nulllist_intlist2(config_data):
	check_vsql(config_data, "[None] < [1]")

def test_nulllist_intlist3(config_data):
	check_vsql(config_data, "[None, None] < [1]")

def test_nulllist_numberlist1(config_data):
	check_vsql(config_data, "[] < [1.1]")

def test_nulllist_numberlist2(config_data):
	check_vsql(config_data, "[None] < [1.1]")

def test_nulllist_numberlist3(config_data):
	check_vsql(config_data, "[None, None] < [1.1]")

def test_nulllist_strlist1(config_data):
	check_vsql(config_data, "[] < ['gurk']")

def test_nulllist_strlist2(config_data):
	check_vsql(config_data, "[None] < ['gurk']")

def test_nulllist_strlist3(config_data):
	check_vsql(config_data, "[None, None] < ['gurk']")

def test_nulllist_datelist1(config_data):
	check_vsql(config_data, "[] < [@(2000-02-29)]")

def test_nulllist_datelist2(config_data):
	check_vsql(config_data, "[None] < [@(2000-02-29)]")

def test_nulllist_datelist3(config_data):
	check_vsql(config_data, "[None, None] < [@(2000-02-29)]")

def test_nulllist_datetimelist1(config_data):
	check_vsql(config_data, "[] < [@(2000-02-29T12:34:56)]")

def test_nulllist_datetimelist2(config_data):
	check_vsql(config_data, "[None] < [@(2000-02-29T12:34:56)]")

def test_nulllist_datetimelist3(config_data):
	check_vsql(config_data, "[None, None] < [@(2000-02-29T12:34:56)]")

def test_intlist_nulllist1(config_data):
	check_vsql(config_data, "not ([1] < [])")

def test_intlist_nulllist2(config_data):
	check_vsql(config_data, "not ([1] < [None])")

def test_intlist_nulllist3(config_data):
	check_vsql(config_data, "not ([1] < [None, None])")

def test_numberlist_nulllist1(config_data):
	check_vsql(config_data, "not ([1.1] < [])")

def test_numberlist_nulllist2(config_data):
	check_vsql(config_data, "not ([1.1] < [None])")

def test_numberlist_nulllist3(config_data):
	check_vsql(config_data, "not ([1.1] < [None, None])")

def test_strlist_nulllist1(config_data):
	check_vsql(config_data, "not (['gurk'] < [])")

def test_strlist_nulllist2(config_data):
	check_vsql(config_data, "not (['gurk'] < [None])")

def test_strlist_nulllist3(config_data):
	check_vsql(config_data, "not (['gurk'] < [None, None])")

def test_datelist_nulllist1(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] < [])")

def test_datelist_nulllist2(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] < [None])")

def test_datelist_nulllist3(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] < [None, None])")

def test_datetimelist_nulllist1(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] < [])")

def test_datetimelist_nulllist2(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] < [None])")

def test_datetimelist_nulllist3(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] < [None, None])")
