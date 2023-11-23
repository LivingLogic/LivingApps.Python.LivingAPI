"""
Tests for vSQL functions.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

import math

from conftest import *


###
### Tests
###

def test_today(config_data):
	check_vsql(config_data, "today() >= @(2000-02-29)")

def test_now(config_data):
	check_vsql(config_data, "now() >= @(2000-02-29T12:34:56)")

def test_bool(config_data):
	check_vsql(config_data, "not bool()")

def test_bool_none(config_data):
	check_vsql(config_data, "not bool(None)")

def test_bool_false(config_data):
	check_vsql(config_data, "not bool(False)")

def test_bool_true(config_data):
	check_vsql(config_data, "bool(True)")

def test_bool_int_none(config_data):
	check_vsql(config_data, "not bool(app.p_int_none.value)")

def test_bool_int_false(config_data):
	check_vsql(config_data, "not bool(0)")

def test_bool_int_true(config_data):
	check_vsql(config_data, "bool(42)")

def test_bool_number_false(config_data):
	check_vsql(config_data, "not bool(0.0)")

def test_bool_number_true(config_data):
	check_vsql(config_data, "bool(42.5)")

def test_bool_datedelta_false(config_data):
	check_vsql(config_data, "not bool(days(0))")

def test_bool_datedelta_true(config_data):
	check_vsql(config_data, "bool(days(42))")

def test_bool_datetimedelta_false(config_data):
	check_vsql(config_data, "not bool(minutes(0))")

def test_bool_datetimedelta_true(config_data):
	check_vsql(config_data, "bool(minutes(42))")

def test_bool_monthdelta_false(config_data):
	check_vsql(config_data, "not bool(monthdelta(0))")

def test_bool_monthdelta_true(config_data):
	check_vsql(config_data, "bool(monthdelta(42))")

def test_bool_date(config_data):
	check_vsql(config_data, "bool(@(2000-02-29))")

def test_bool_datetime(config_data):
	check_vsql(config_data, "bool(@(2000-02-29T12:34:56))")

def test_bool_color(config_data):
	check_vsql(config_data, "bool(#fff)")

def test_bool_str_false(config_data):
	check_vsql(config_data, "not bool('')")

def test_bool_str_true(config_data):
	check_vsql(config_data, "bool('gurk')")

def test_bool_intlist(config_data):
	check_vsql(config_data, "bool([42])")

def test_bool_numberlist(config_data):
	check_vsql(config_data, "bool([42.5])")

def test_bool_strlist(config_data):
	check_vsql(config_data, "bool(['gurk'])")

def test_bool_datelist(config_data):
	check_vsql(config_data, "bool([today()])")

def test_bool_datetimelist(config_data):
	check_vsql(config_data, "bool([now()])")

def test_bool_intset(config_data):
	check_vsql(config_data, "bool({42})")

def test_bool_numberset(config_data):
	check_vsql(config_data, "bool({42.5})")

def test_bool_strset(config_data):
	check_vsql(config_data, "bool({'gurk'})")

def test_bool_dateset(config_data):
	check_vsql(config_data, "bool({today()})")

def test_bool_datetimeset(config_data):
	check_vsql(config_data, "bool({now()})")

def test_int(config_data):
	check_vsql(config_data, "not int()")

def test_int_bool_false(config_data):
	check_vsql(config_data, "not int(False)")

def test_int_bool_true(config_data):
	check_vsql(config_data, "int(True)")

def test_int_int(config_data):
	check_vsql(config_data, "int(42) == 42")

def test_int_number(config_data):
	check_vsql(config_data, "int(42.4) == 42")

def test_int_str_ok(config_data):
	check_vsql(config_data, "int('42') == 42")

def test_int_str_bad(config_data):
	check_vsql(config_data, "int('42.5') is None")

def test_int_str_very_bad(config_data):
	check_vsql(config_data, "int('verybad') is None")

def test_float(config_data):
	check_vsql(config_data, "float() == 0.0")

def test_float_bool_false(config_data):
	check_vsql(config_data, "float(False) == 0.0")

def test_float_bool_true(config_data):
	check_vsql(config_data, "float(True) == 1.0")

def test_float_int(config_data):
	check_vsql(config_data, "float(42) == 42.0")

def test_float_number(config_data):
	check_vsql(config_data, "float(42.5) == 42.5")

def test_float_str(config_data):
	check_vsql(config_data, "float('42.5') == 42.5")

def test_float_str_bad(config_data):
	check_vsql(config_data, "float('bad') is None")

def test_str(config_data):
	check_vsql(config_data, "str() is None")

def test_str_bool_false(config_data):
	check_vsql(config_data, "str(False) == 'False'")

def test_str_bool_true(config_data):
	check_vsql(config_data, "str(True) == 'True'")

def test_str_int(config_data):
	check_vsql(config_data, "str(-42) == '-42'")

def test_str_number(config_data):
	check_vsql(config_data, "str(42.0) == '42.0' and str(-42.5) == '-42.5'")

def test_str_str(config_data):
	check_vsql(config_data, "str('foo') == 'foo'")

def test_str_date(config_data):
	check_vsql(config_data, "str(@(2000-02-29)) == '2000-02-29'")

def test_str_datetime(config_data):
	check_vsql(config_data, "str(@(2000-02-29T12:34:56)) == '2000-02-29 12:34:56'")

def test_str_datedelta_1(config_data):
	check_vsql(config_data, "str(days(1)) == '1 day'")

def test_str_datedelta_2(config_data):
	check_vsql(config_data, "str(days(42)) == '42 days'")

def test_str_datetimedelta_1(config_data):
	check_vsql(config_data, "str(seconds(42)) == '0:00:42'")

def test_str_datetimedelta_2(config_data):
	check_vsql(config_data, "str(minutes(42)) == '0:42:00'")

def test_str_datetimedelta_3(config_data):
	check_vsql(config_data, "str(hours(17) + minutes(23)) == '17:23:00'")

def test_str_datetimedelta_4(config_data):
	check_vsql(config_data, "str(hours(42) + seconds(0)) == '1 day, 18:00:00'")

def test_str_datetimedelta_5(config_data):
	check_vsql(config_data, "str(days(42) + seconds(0)) == '42 days, 0:00:00'")

def test_str_datetimedelta_6(config_data):
	check_vsql(config_data, "str(days(42) + hours(17) + minutes(23)) == '42 days, 17:23:00'")

def test_str_datetimedelta_7(config_data):
	check_vsql(config_data, "str(-days(1) - hours(12) - minutes(34) - seconds(56)) == '-2 days, 11:25:04'")

def test_str_monthdelta_1(config_data):
	check_vsql(config_data, "str(monthdelta(0)) == '0 months'")

def test_str_monthdelta_2(config_data):
	check_vsql(config_data, "str(monthdelta(1)) == '1 month'")

def test_str_monthdelta_3(config_data):
	check_vsql(config_data, "str(monthdelta(42)) == '42 months'")

def test_str_color_1(config_data):
	check_vsql(config_data, "str(#000f) == '#000'")

def test_str_color_2(config_data):
	check_vsql(config_data, "str(#fff0) == 'rgba(255, 255, 255, 0.000)'")

def test_str_color_3(config_data):
	check_vsql(config_data, "str(#123456) == '#123456'")

def test_str_color_4(config_data):
	check_vsql(config_data, "str(#12345678) == 'rgba(18, 52, 86, 0.471)'")

def test_str_geo_without_info(config_data):
	check_vsql(config_data, "str(geo(49.95, 11.59)) == '<geo lat=49.95 long=11.59 info=None>'")

def test_str_geo_with_info(config_data):
	check_vsql(config_data, "str(geo(49.95, 11.59, 'Here')) == '<geo lat=49.95 long=11.59 info=\\'Here\\'>'")

def test_str_intlist(config_data):
	check_vsql(config_data, "str([1, 2, 3, None]) == '[1, 2, 3, None]'")

def test_str_numberlist(config_data):
	check_vsql(config_data, "str([1.2, 3.4, 5.6, None]) == '[1.2, 3.4, 5.6, None]'")

def test_str_strlist(config_data):
	check_vsql(config_data, "str(['foo', 'bar', None]) == '[\\'foo\\', \\'bar\\', None]'")

def test_str_datelist(config_data):
	check_vsql(config_data, "str([@(2000-02-29), None]) == '[@(2000-02-29), None]'")

def test_str_datetimelist(config_data):
	check_vsql(config_data, "str([@(2000-02-29T12:34:56), None]) == '[@(2000-02-29T12:34:56), None]'")

# For the set test only include one non-``None`` value,
# as the order of the other elements is undefined

def test_str_intset(config_data):
	check_vsql(config_data, "str({1, None}) == '{1, None}'")

def test_str_numberset(config_data):
	check_vsql(config_data, "str({1.2, None}) == '{1.2, None}'")

def test_str_strset(config_data):
	check_vsql(config_data, "str({'foo', None}) == '{\\'foo\\', None}'")

def test_str_dateset(config_data):
	check_vsql(config_data, "str({@(2000-02-29), None}) == '{@(2000-02-29), None}'")

def test_str_datetimeset(config_data):
	check_vsql(config_data, "str({@(2000-02-29T12:34:56), None}) == '{@(2000-02-29T12:34:56), None}'")

def test_repr_none(config_data):
	check_vsql(config_data, "repr(None) == 'None'")

def test_repr_bool_false(config_data):
	check_vsql(config_data, "repr(False) == 'False'")

def test_repr_bool_True(config_data):
	check_vsql(config_data, "repr(True) == 'True'")

def test_repr_int(config_data):
	check_vsql(config_data, "repr(-42) == '-42'")

def test_repr_number_1(config_data):
	check_vsql(config_data, "repr(42.0) == '42.0'")

def test_repr_number_2(config_data):
	check_vsql(config_data, "repr(-42.5) == '-42.5'")

def test_repr_str(config_data):
	check_vsql(config_data, "repr('foo\"bar') == '\\'foo\\\"bar\\''")

def test_repr_date(config_data):
	check_vsql(config_data, "repr(@(2000-02-29)) == '@(2000-02-29)'")

def test_repr_datetime(config_data):
	check_vsql(config_data, "repr(@(2000-02-29T12:34:56)) == '@(2000-02-29T12:34:56)'")

def test_repr_datedelta_1(config_data):
	check_vsql(config_data, "repr(days(1)) == 'timedelta(1)'")

def test_repr_datedelta_2(config_data):
	check_vsql(config_data, "repr(days(42)) == 'timedelta(42)'")

def test_repr_datetimedelta_1(config_data):
	# FIXME: Oracle doesn't have enough precision for seconds
	check_vsql(config_data, "repr(seconds(42)) == 'timedelta(0, 42)'")

def test_repr_datetimedelta_2(config_data):
	check_vsql(config_data, "repr(minutes(42)) == 'timedelta(0, 2520)'")

def test_repr_datetimedelta_3(config_data):
	check_vsql(config_data, "repr(hours(17) + minutes(23)) == 'timedelta(0, 62580)'")

def test_repr_datetimedelta_4(config_data):
	check_vsql(config_data, "repr(hours(42) + seconds(0)) == 'timedelta(1, 64800)'")

def test_repr_datetimedelta_5(config_data):
	check_vsql(config_data, "repr(days(42) + seconds(0)) == 'timedelta(42)'")

def test_repr_datetimedelta_6(config_data):
	check_vsql(config_data, "repr(days(42) + hours(17) + minutes(23)) == 'timedelta(42, 62580)'")

def test_repr_monthdelta(config_data):
	check_vsql(config_data, "repr(monthdelta(42)) == 'monthdelta(42)'")

def test_repr_color_1(config_data):
	check_vsql(config_data, "repr(#000) == '#000'")

def test_repr_color_2(config_data):
	check_vsql(config_data, "repr(#369c) == '#369c'")

def test_repr_color_3(config_data):
	check_vsql(config_data, "repr(#123456) == '#123456'")

def test_repr_color_4(config_data):
	check_vsql(config_data, "repr(#12345678) == '#12345678'")

def test_repr_geo_without_info(config_data):
	check_vsql(config_data, "repr(geo(49.95, 11.59)) == '<geo lat=49.95 long=11.59 info=None>'")

def test_repr_geo_with_info(config_data):
	check_vsql(config_data, "repr(geo(49.95, 11.59, 'Here')) == '<geo lat=49.95 long=11.59 info=\\'Here\\'>'")

def test_repr_intlist(config_data):
	check_vsql(config_data, "repr([1, 2, 3, None]) == '[1, 2, 3, None]'")

def test_repr_numberlist(config_data):
	check_vsql(config_data, "repr([1.2, 3.4, 5.6, None]) == '[1.2, 3.4, 5.6, None]'")

def test_repr_strlist(config_data):
	check_vsql(config_data, "repr(['foo', 'bar', None]) == '[\\'foo\\', \\'bar\\', None]'")

def test_repr_datelist(config_data):
	check_vsql(config_data, "repr([@(2000-02-29), None]) == '[@(2000-02-29), None]'")

def test_repr_datetimelist(config_data):
	check_vsql(config_data, "repr([@(2000-02-29T12:34:56), None]) == '[@(2000-02-29T12:34:56), None]'")

# For the set test only include one non-``None`` value,
# as the order of the other elements is undefined

def test_repr_intset(config_data):
	check_vsql(config_data, "repr({1, None}) == '{1, None}'")

def test_repr_numberset(config_data):
	check_vsql(config_data, "repr({1.2, None}) == '{1.2, None}'")

def test_repr_strset(config_data):
	check_vsql(config_data, "repr({'foo', None}) == '{\\\'foo\\\', None}'")

def test_repr_dateset(config_data):
	check_vsql(config_data, "repr({@(2000-02-29), None}) == '{@(2000-02-29), None}'")

def test_repr_datetimeset(config_data):
	check_vsql(config_data, "repr({@(2000-02-29T12:34:56), None}) == '{@(2000-02-29T12:34:56), None}'")

def test_date_int(config_data):
	check_vsql(config_data, "date(2000, 2, 29) == @(2000-02-29)")

def test_date_datetime(config_data):
	check_vsql(config_data, "date(@(2000-02-29T12:34:56)) == @(2000-02-29)")

def test_datetime_int3(config_data):
	check_vsql(config_data, "datetime(2000, 2, 29) == @(2000-02-29T)")

def test_datetime_int4(config_data):
	check_vsql(config_data, "datetime(2000, 2, 29, 12) == @(2000-02-29T12:00:00)")

def test_datetime_int5(config_data):
	check_vsql(config_data, "datetime(2000, 2, 29, 12, 34) == @(2000-02-29T12:34:00)")

def test_datetime_int6(config_data):
	check_vsql(config_data, "datetime(2000, 2, 29, 12, 34, 56) == @(2000-02-29T12:34:56)")

def test_datetime_date(config_data):
	check_vsql(config_data, "datetime(@(2000-02-29)) == @(2000-02-29T00:00:00)")

def test_datetime_date_int1(config_data):
	check_vsql(config_data, "datetime(@(2000-02-29), 12) == @(2000-02-29T12:00:00)")

def test_datetime_date_int2(config_data):
	check_vsql(config_data, "datetime(@(2000-02-29), 12, 34) == @(2000-02-29T12:34:00)")

def test_datetime_date_int3(config_data):
	check_vsql(config_data, "datetime(@(2000-02-29), 12, 34, 56) == @(2000-02-29T12:34:56)")

def test_len_str1(config_data):
	check_vsql(config_data, "len('') == 0")

def test_len_str2(config_data):
	check_vsql(config_data, "len('gurk') == 4")

def test_len_str3(config_data):
	check_vsql(config_data, "len('\\t\\n') == 2")

def test_len_intlist(config_data):
	check_vsql(config_data, "len([1, 2, 3]) == 3")

def test_len_numberlist(config_data):
	check_vsql(config_data, "len([1.2, 3.4, 5.6]) == 3")

def test_len_strlist(config_data):
	check_vsql(config_data, "len(['foo', 'bar', 'baz']) == 3")

def test_len_datelist(config_data):
	check_vsql(config_data, "len([@(2000-02-29), @(2000-02-29), @(2000-03-01)]) == 3")

def test_len_datetimelist(config_data):
	check_vsql(config_data, "len([@(2000-02-29T12:34:56), @(2000-02-29T12:34:56), @(2000-03-01T12:34:56)]) == 3")

def test_len_intset(config_data):
	check_vsql(config_data, "len({1, 1, 2, 2, 3, 3, None, None}) == 4")

def test_len_numberset(config_data):
	check_vsql(config_data, "len({1.2, 3.4, 5.6, None, 1.2, 3.4, 5.6, None}) == 4")

def test_len_strset(config_data):
	check_vsql(config_data, "len({'foo', 'bar', 'baz', None, 'foo', 'bar', 'baz'}) == 4")

def test_len_dateset(config_data):
	check_vsql(config_data, "len({@(2000-02-29), @(2000-02-29), @(2000-03-21), None}) == 3")

def test_len_datetimeset(config_data):
	check_vsql(config_data, "len({@(2000-02-29T12:34:56), None, @(2000-02-29T12:34:56), None, @(2000-02-29T11:22:33)}) == 3")

def test_timedelta(config_data):
	check_vsql(config_data, "not timedelta()")

def test_timedelta_int1(config_data):
	check_vsql(config_data, "timedelta(42)")

def test_timedelta_int2(config_data):
	check_vsql(config_data, "timedelta(42, 12)")

def test_monthdelta(config_data):
	check_vsql(config_data, "not monthdelta()")

def test_monthdelta_int(config_data):
	check_vsql(config_data, "monthdelta(42)")

def test_years(config_data):
	check_vsql(config_data, "years(25)")

def test_months(config_data):
	check_vsql(config_data, "months(3)")

def test_weeks(config_data):
	check_vsql(config_data, "weeks(3)")

def test_days(config_data):
	check_vsql(config_data, "days(12)")

def test_hours(config_data):
	check_vsql(config_data, "hours(8)")

def test_minutes(config_data):
	check_vsql(config_data, "minutes(45)")

def test_seconds(config_data):
	check_vsql(config_data, "seconds(60)")

def test_md5(config_data):
	check_vsql(config_data, "md5('gurk') == '4b5b6a3fa4af2541daa569277c7ff4c5'")

def test_random(config_data):
	check_vsql(config_data, "random() + 1")

def test_randrange(config_data):
	check_vsql(config_data, "randrange(1, 10)")

def test_seq(config_data):
	check_vsql(config_data, "seq()")

def test_rgb1(config_data):
	check_vsql(config_data, "rgb(0.2, 0.4, 0.6) == #369")

def test_rgb2(config_data):
	check_vsql(config_data, "rgb(0.2, 0.4, 0.6, 0.8) == #369c")

def test_list_str(config_data):
	check_vsql(config_data, "list('gurk') == ['g', 'u', 'r', 'k']")

def test_list_intlist(config_data):
	check_vsql(config_data, "list([1, 2, 3]) == [1, 2, 3]")

def test_list_numberlist(config_data):
	check_vsql(config_data, "list([1.2, 3.4, 5.6]) == [1.2, 3.4, 5.6]")

def test_list_strlist(config_data):
	check_vsql(config_data, "list(['foo', 'bar', 'baz', None]) == ['foo', 'bar', 'baz', None]")

def test_list_datelist(config_data):
	check_vsql(config_data, "list([@(2000-02-29), @(2000-03-01), None]) == [@(2000-02-29), @(2000-03-01), None]")

def test_list_datetimelist(config_data):
	check_vsql(config_data, "list([@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), None]) == [@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), None]")

def test_list_intset(config_data):
	check_vsql(config_data, "list({1, None}) == [1, None]")

def test_list_numberset(config_data):
	check_vsql(config_data, "list({1.2, None}) == [1.2, None]")

def test_list_strset(config_data):
	check_vsql(config_data, "list({'foo', None}) == ['foo', None]")

def test_list_dateset(config_data):
	check_vsql(config_data, "list({@(2000-02-29), None}) == [@(2000-02-29), None]")

def test_list_datetimeset(config_data):
	check_vsql(config_data, "list({@(2000-02-29T12:34:56), None}) == [@(2000-02-29T12:34:56), None]")

def test_set_str(config_data):
	check_vsql(config_data, "set('mississippi') == {'i', 'm', 'p', 's'}")

def test_set_intlist(config_data):
	check_vsql(config_data, "set([1, 2, 3, 2, 1, None]) == {1, 2, 3, None}")

def test_set_numberlist(config_data):
	check_vsql(config_data, "set([1.2, 3.4, 5.6, 3.4, 1.2, None]) == {1.2, 3.4, 5.6, None}")

def test_set_strlist(config_data):
	check_vsql(config_data, "set(['foo', 'bar', 'baz', None, 'baz', 'bar', 'foo']) == {'foo', 'bar', 'baz', None}")

def test_set_datelist(config_data):
	check_vsql(config_data, "set([@(2000-02-29), @(2000-03-01), None, @(2000-03-01), @(2000-02-29)]) == {@(2000-02-29), @(2000-03-01), None}")

def test_set_datetimelist(config_data):
	check_vsql(config_data, "set([@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), @(2000-02-29T11:22:33), None, @(2000-02-29T12:34:56)]) == {@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), None}")

def test_set_intset(config_data):
	check_vsql(config_data, "set({1, None}) == {1, None}")

def test_set_numberset(config_data):
	check_vsql(config_data, "set({1.2, None}) == {1.2, None}")

def test_set_strset(config_data):
	check_vsql(config_data, "set({'foo', None}) == {'foo', None}")

def test_set_dateset(config_data):
	check_vsql(config_data, "set({@(2000-02-29), None}) == {@(2000-02-29), None}")

def test_set_datetimeset(config_data):
	check_vsql(config_data, "set({@(2000-02-29T12:34:56), None}) == {@(2000-02-29T12:34:56), None}")

def test_dist(config_data):
	check_vsql(config_data, "abs(dist(geo(49.95, 11.59, 'Here'), geo(12.34, 56.67, 'There')) - 5845.77551787602) < 1e-5")

def test_abs(config_data):
	check_vsql(config_data, "abs(-42) == 42")

def test_cos_bool(config_data):
	check_vsql(config_data, "cos(False) == 1")

def test_cos_int(config_data):
	check_vsql(config_data, "cos(0) == 1")

def test_cos_number1(config_data):
	check_vsql(config_data, "cos(0.0) == 1")

def test_cos_number2(config_data):
	check_vsql(config_data, f"abs(cos({math.pi} / 2)) < 1e-10")

def test_cos_number3(config_data):
	check_vsql(config_data, f"abs(cos({math.pi}) + 1) < 1e-10")

def test_sin_bool(config_data):
	check_vsql(config_data, "sin(False) == 0")

def test_sin_int(config_data):
	check_vsql(config_data, "sin(0) == 0")

def test_sin_number1(config_data):
	check_vsql(config_data, "sin(0.0) == 0")

def test_sin_number2(config_data):
	check_vsql(config_data, f"abs(sin({math.pi} / 2) - 1) < 1e-10")

def test_sin_number3(config_data):
	check_vsql(config_data, f"abs(sin({math.pi})) < 1e-10")

def test_tan_bool(config_data):
	check_vsql(config_data, "tan(False) == 0")

def test_tan_int(config_data):
	check_vsql(config_data, "tan(0) == 0")

def test_tan_number1(config_data):
	check_vsql(config_data, "tan(0.0) == 0")

def test_tan_number2(config_data):
	check_vsql(config_data, f"abs(tan(0.25 * {math.pi}) - 1) < 1e-10")

def test_tan_number3(config_data):
	check_vsql(config_data, f"abs(tan(0.75 * {math.pi}) + 1) < 1e-10")

def test_sqrt_bool1(config_data):
	check_vsql(config_data, "sqrt(False) == 0.0")

def test_sqrt_bool2(config_data):
	check_vsql(config_data, "sqrt(True) == 1.0")

def test_sqrt_int1(config_data):
	check_vsql(config_data, "sqrt(16) == 4.0")

def test_sqrt_int2(config_data):
	check_vsql(config_data, "sqrt(-16) is None")

def test_sqrt_number1(config_data):
	check_vsql(config_data, "sqrt(16.0) == 4.0")

def test_sqrt_number2(config_data):
	check_vsql(config_data, "sqrt(-16.0) is None")
