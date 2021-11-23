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

def test_today(config_persons):
	check_vsql(config_persons, "today() >= @(2000-02-29)")

def test_now(config_persons):
	check_vsql(config_persons, "now() >= @(2000-02-29T12:34:56)")

def test_bool(config_persons):
	check_vsql(config_persons, "not bool()")

def test_bool_none(config_persons):
	check_vsql(config_persons, "not bool(None)")

def test_bool_false(config_persons):
	check_vsql(config_persons, "not bool(False)")

def test_bool_true(config_persons):
	check_vsql(config_persons, "bool(True)")

def test_bool_int_none(config_persons):
	check_vsql(config_persons, "not bool(app.p_int_none.value)")

def test_bool_int_false(config_persons):
	check_vsql(config_persons, "not bool(0)")

def test_bool_int_true(config_persons):
	check_vsql(config_persons, "bool(42)")

def test_bool_number_false(config_persons):
	check_vsql(config_persons, "not bool(0.0)")

def test_bool_number_true(config_persons):
	check_vsql(config_persons, "bool(42.5)")

def test_bool_datedelta_false(config_persons):
	check_vsql(config_persons, "not bool(days(0))")

def test_bool_datedelta_true(config_persons):
	check_vsql(config_persons, "bool(days(42))")

def test_bool_datetimedelta_false(config_persons):
	check_vsql(config_persons, "not bool(minutes(0))")

def test_bool_datetimedelta_true(config_persons):
	check_vsql(config_persons, "bool(minutes(42))")

def test_bool_monthdelta_false(config_persons):
	check_vsql(config_persons, "not bool(monthdelta(0))")

def test_bool_monthdelta_true(config_persons):
	check_vsql(config_persons, "bool(monthdelta(42))")

def test_bool_date(config_persons):
	check_vsql(config_persons, "bool(@(2000-02-29))")

def test_bool_datetime(config_persons):
	check_vsql(config_persons, "bool(@(2000-02-29T12:34:56))")

def test_bool_color(config_persons):
	check_vsql(config_persons, "bool(#fff)")

def test_bool_str_false(config_persons):
	check_vsql(config_persons, "not bool('')")

def test_bool_str_true(config_persons):
	check_vsql(config_persons, "bool('gurk')")

def test_bool_intlist(config_persons):
	check_vsql(config_persons, "bool([42])")

def test_bool_numberlist(config_persons):
	check_vsql(config_persons, "bool([42.5])")

def test_bool_strlist(config_persons):
	check_vsql(config_persons, "bool(['gurk'])")

def test_bool_datelist(config_persons):
	check_vsql(config_persons, "bool([today()])")

def test_bool_datetimelist(config_persons):
	check_vsql(config_persons, "bool([now()])")

def test_bool_intset(config_persons):
	check_vsql(config_persons, "bool({42})")

def test_bool_numberset(config_persons):
	check_vsql(config_persons, "bool({42.5})")

def test_bool_strset(config_persons):
	check_vsql(config_persons, "bool({'gurk'})")

def test_bool_dateset(config_persons):
	check_vsql(config_persons, "bool({today()})")

def test_bool_datetimeset(config_persons):
	check_vsql(config_persons, "bool({now()})")

def test_int(config_persons):
	check_vsql(config_persons, "not int()")

def test_int_bool_false(config_persons):
	check_vsql(config_persons, "not int(False)")

def test_int_bool_true(config_persons):
	check_vsql(config_persons, "int(True)")

def test_int_int(config_persons):
	check_vsql(config_persons, "int(42) == 42")

def test_int_number(config_persons):
	check_vsql(config_persons, "int(42.4) == 42")

def test_int_str_ok(config_persons):
	check_vsql(config_persons, "int('42') == 42")

def test_int_str_bad(config_persons):
	check_vsql(config_persons, "int('42.5') is None")

def test_int_str_very_bad(config_persons):
	check_vsql(config_persons, "int('verybad') is None")

def test_float(config_persons):
	check_vsql(config_persons, "float() == 0.0")

def test_float_bool_false(config_persons):
	check_vsql(config_persons, "float(False) == 0.0")

def test_float_bool_true(config_persons):
	check_vsql(config_persons, "float(True) == 1.0")

def test_float_int(config_persons):
	check_vsql(config_persons, "float(42) == 42.0")

def test_float_number(config_persons):
	check_vsql(config_persons, "float(42.5) == 42.5")

def test_float_str(config_persons):
	check_vsql(config_persons, "float('42.5') == 42.5")

def test_float_str_bad(config_persons):
	check_vsql(config_persons, "float('bad') is None")

def test_str(config_persons):
	check_vsql(config_persons, "str() is None")

def test_str_bool_false(config_persons):
	check_vsql(config_persons, "str(False) == 'False'")

def test_str_bool_true(config_persons):
	check_vsql(config_persons, "str(True) == 'True'")

def test_str_int(config_persons):
	check_vsql(config_persons, "str(-42) == '-42'")

def test_str_number(config_persons):
	check_vsql(config_persons, "str(42.0) == '42.0' and str(-42.5) == '-42.5'")

def test_str_str(config_persons):
	check_vsql(config_persons, "str('foo') == 'foo'")

def test_str_date(config_persons):
	check_vsql(config_persons, "str(@(2000-02-29)) == '2000-02-29'")

def test_str_datetime(config_persons):
	check_vsql(config_persons, "str(@(2000-02-29T12:34:56)) == '2000-02-29 12:34:56'")

def test_str_datedelta_1(config_persons):
	check_vsql(config_persons, "str(days(1)) == '1 day'")

def test_str_datedelta_2(config_persons):
	check_vsql(config_persons, "str(days(42)) == '42 days'")

def test_str_datetimedelta_1(config_persons):
	check_vsql(config_persons, "str(seconds(42)) == '0:00:42'")

def test_str_datetimedelta_2(config_persons):
	check_vsql(config_persons, "str(minutes(42)) == '0:42:00'")

def test_str_datetimedelta_3(config_persons):
	check_vsql(config_persons, "str(hours(17) + minutes(23)) == '17:23:00'")

def test_str_datetimedelta_4(config_persons):
	check_vsql(config_persons, "str(hours(42) + seconds(0)) == '1 day, 18:00:00'")

def test_str_datetimedelta_5(config_persons):
	check_vsql(config_persons, "str(days(42) + seconds(0)) == '42 days, 0:00:00'")

def test_str_datetimedelta_6(config_persons):
	check_vsql(config_persons, "str(days(42) + hours(17) + minutes(23)) == '42 days, 17:23:00'")

def test_str_datetimedelta_7(config_persons):
	check_vsql(config_persons, "str(-days(1) - hours(12) - minutes(34) - seconds(56)) == '-2 days, 11:25:04'")

def test_str_monthdelta_1(config_persons):
	check_vsql(config_persons, "str(monthdelta(0)) == '0 months'")

def test_str_monthdelta_2(config_persons):
	check_vsql(config_persons, "str(monthdelta(1)) == '1 month'")

def test_str_monthdelta_3(config_persons):
	check_vsql(config_persons, "str(monthdelta(42)) == '42 months'")

def test_str_color_1(config_persons):
	check_vsql(config_persons, "str(#000f) == '#000'")

def test_str_color_2(config_persons):
	check_vsql(config_persons, "str(#fff0) == 'rgba(255, 255, 255, 0.000)'")

def test_str_color_3(config_persons):
	check_vsql(config_persons, "str(#123456) == '#123456'")

def test_str_color_4(config_persons):
	check_vsql(config_persons, "str(#12345678) == 'rgba(18, 52, 86, 0.471)'")

def test_str_geo_without_info(config_persons):
	check_vsql(config_persons, "str(geo(49.95, 11.59)) == '<geo lat=49.95 long=11.59 info=None>'")

def test_str_geo_with_info(config_persons):
	check_vsql(config_persons, "str(geo(49.95, 11.59, 'Here')) == '<geo lat=49.95 long=11.59 info=\\'Here\\'>'")

def test_str_intlist(config_persons):
	check_vsql(config_persons, "str([1, 2, 3, None]) == '[1, 2, 3, None]'")

def test_str_numberlist(config_persons):
	check_vsql(config_persons, "str([1.2, 3.4, 5.6, None]) == '[1.2, 3.4, 5.6, None]'")

def test_str_strlist(config_persons):
	check_vsql(config_persons, "str(['foo', 'bar', None]) == '[\\'foo\\', \\'bar\\', None]'")

def test_str_datelist(config_persons):
	check_vsql(config_persons, "str([@(2000-02-29), None]) == '[@(2000-02-29), None]'")

def test_str_datetimelist(config_persons):
	check_vsql(config_persons, "str([@(2000-02-29T12:34:56), None]) == '[@(2000-02-29T12:34:56), None]'")

# For the set test only include one non-``None`` value,
# as the order of the other elements is undefined

def test_str_intset(config_persons):
	check_vsql(config_persons, "str({1, None}) == '{1, None}'")

def test_str_numberset(config_persons):
	check_vsql(config_persons, "str({1.2, None}) == '{1.2, None}'")

def test_str_strset(config_persons):
	check_vsql(config_persons, "str({'foo', None}) == '{\\'foo\\', None}'")

def test_str_dateset(config_persons):
	check_vsql(config_persons, "str({@(2000-02-29), None}) == '{@(2000-02-29), None}'")

def test_str_datetimeset(config_persons):
	check_vsql(config_persons, "str({@(2000-02-29T12:34:56), None}) == '{@(2000-02-29T12:34:56), None}'")

def test_repr_none(config_persons):
	check_vsql(config_persons, "repr(None) == 'None'")

def test_repr_bool_false(config_persons):
	check_vsql(config_persons, "repr(False) == 'False'")

def test_repr_bool_True(config_persons):
	check_vsql(config_persons, "repr(True) == 'True'")

def test_repr_int(config_persons):
	check_vsql(config_persons, "repr(-42) == '-42'")

def test_repr_number_1(config_persons):
	check_vsql(config_persons, "repr(42.0) == '42.0'")

def test_repr_number_2(config_persons):
	check_vsql(config_persons, "repr(-42.5) == '-42.5'")

def test_repr_str(config_persons):
	check_vsql(config_persons, "repr('foo\"bar') == '\\'foo\\\"bar\\''")

def test_repr_date(config_persons):
	check_vsql(config_persons, "repr(@(2000-02-29)) == '@(2000-02-29)'")

def test_repr_datetime(config_persons):
	check_vsql(config_persons, "repr(@(2000-02-29T12:34:56)) == '@(2000-02-29T12:34:56)'")

def test_repr_datedelta_1(config_persons):
	check_vsql(config_persons, "repr(days(1)) == 'timedelta(1)'")

def test_repr_datedelta_2(config_persons):
	check_vsql(config_persons, "repr(days(42)) == 'timedelta(42)'")

def test_repr_datetimedelta_1(config_persons):
	# FIXME: Oracle doesn't have enough precision for seconds
	check_vsql(config_persons, "repr(seconds(42)) == 'timedelta(0, 42)'")

def test_repr_datetimedelta_2(config_persons):
	check_vsql(config_persons, "repr(minutes(42)) == 'timedelta(0, 2520)'")

def test_repr_datetimedelta_3(config_persons):
	check_vsql(config_persons, "repr(hours(17) + minutes(23)) == 'timedelta(0, 62580)'")

def test_repr_datetimedelta_4(config_persons):
	check_vsql(config_persons, "repr(hours(42) + seconds(0)) == 'timedelta(1, 64800)'")

def test_repr_datetimedelta_5(config_persons):
	check_vsql(config_persons, "repr(days(42) + seconds(0)) == 'timedelta(42)'")

def test_repr_datetimedelta_6(config_persons):
	check_vsql(config_persons, "repr(days(42) + hours(17) + minutes(23)) == 'timedelta(42, 62580)'")

def test_repr_monthdelta(config_persons):
	check_vsql(config_persons, "repr(monthdelta(42)) == 'monthdelta(42)'")

def test_repr_color_1(config_persons):
	check_vsql(config_persons, "repr(#000) == '#000'")

def test_repr_color_2(config_persons):
	check_vsql(config_persons, "repr(#369c) == '#369c'")

def test_repr_color_3(config_persons):
	check_vsql(config_persons, "repr(#123456) == '#123456'")

def test_repr_color_4(config_persons):
	check_vsql(config_persons, "repr(#12345678) == '#12345678'")

def test_repr_geo_without_info(config_persons):
	check_vsql(config_persons, "repr(geo(49.95, 11.59)) == '<geo lat=49.95 long=11.59 info=None>'")

def test_repr_geo_with_info(config_persons):
	check_vsql(config_persons, "repr(geo(49.95, 11.59, 'Here')) == '<geo lat=49.95 long=11.59 info=\\'Here\\'>'")

def test_repr_intlist(config_persons):
	check_vsql(config_persons, "repr([1, 2, 3, None]) == '[1, 2, 3, None]'")

def test_repr_numberlist(config_persons):
	check_vsql(config_persons, "repr([1.2, 3.4, 5.6, None]) == '[1.2, 3.4, 5.6, None]'")

def test_repr_strlist(config_persons):
	check_vsql(config_persons, "repr(['foo', 'bar', None]) == '[\\'foo\\', \\'bar\\', None]'")

def test_repr_datelist(config_persons):
	check_vsql(config_persons, "repr([@(2000-02-29), None]) == '[@(2000-02-29), None]'")

def test_repr_datetimelist(config_persons):
	check_vsql(config_persons, "repr([@(2000-02-29T12:34:56), None]) == '[@(2000-02-29T12:34:56), None]'")

# For the set test only include one non-``None`` value,
# as the order of the other elements is undefined

def test_repr_intset(config_persons):
	check_vsql(config_persons, "repr({1, None}) == '{1, None}'")

def test_repr_numberset(config_persons):
	check_vsql(config_persons, "repr({1.2, None}) == '{1.2, None}'")

def test_repr_strset(config_persons):
	check_vsql(config_persons, "repr({'foo', None}) == '{\\\'foo\\\', None}'")

def test_repr_dateset(config_persons):
	check_vsql(config_persons, "repr({@(2000-02-29), None}) == '{@(2000-02-29), None}'")

def test_repr_datetimeset(config_persons):
	check_vsql(config_persons, "repr({@(2000-02-29T12:34:56), None}) == '{@(2000-02-29T12:34:56), None}'")

def test_date_int(config_persons):
	check_vsql(config_persons, "date(2000, 2, 29) == @(2000-02-29)")

def test_date_datetime(config_persons):
	check_vsql(config_persons, "date(@(2000-02-29T12:34:56)) == @(2000-02-29)")

def test_datetime_int3(config_persons):
	check_vsql(config_persons, "datetime(2000, 2, 29) == @(2000-02-29T)")

def test_datetime_int4(config_persons):
	check_vsql(config_persons, "datetime(2000, 2, 29, 12) == @(2000-02-29T12:00:00)")

def test_datetime_int5(config_persons):
	check_vsql(config_persons, "datetime(2000, 2, 29, 12, 34) == @(2000-02-29T12:34:00)")

def test_datetime_int6(config_persons):
	check_vsql(config_persons, "datetime(2000, 2, 29, 12, 34, 56) == @(2000-02-29T12:34:56)")

def test_datetime_date(config_persons):
	check_vsql(config_persons, "datetime(@(2000-02-29)) == @(2000-02-29T00:00:00)")

def test_datetime_date_int1(config_persons):
	check_vsql(config_persons, "datetime(@(2000-02-29), 12) == @(2000-02-29T12:00:00)")

def test_datetime_date_int2(config_persons):
	check_vsql(config_persons, "datetime(@(2000-02-29), 12, 34) == @(2000-02-29T12:34:00)")

def test_datetime_date_int3(config_persons):
	check_vsql(config_persons, "datetime(@(2000-02-29), 12, 34, 56) == @(2000-02-29T12:34:56)")

def test_len_str1(config_persons):
	check_vsql(config_persons, "len('') == 0")

def test_len_str2(config_persons):
	check_vsql(config_persons, "len('gurk') == 4")

def test_len_str3(config_persons):
	check_vsql(config_persons, "len('\\t\\n') == 2")

def test_len_intlist(config_persons):
	check_vsql(config_persons, "len([1, 2, 3]) == 3")

def test_len_numberlist(config_persons):
	check_vsql(config_persons, "len([1.2, 3.4, 5.6]) == 3")

def test_len_strlist(config_persons):
	check_vsql(config_persons, "len(['foo', 'bar', 'baz']) == 3")

def test_len_datelist(config_persons):
	check_vsql(config_persons, "len([@(2000-02-29), @(2000-02-29), @(2000-03-01)]) == 3")

def test_len_datetimelist(config_persons):
	check_vsql(config_persons, "len([@(2000-02-29T12:34:56), @(2000-02-29T12:34:56), @(2000-03-01T12:34:56)]) == 3")

def test_len_intset(config_persons):
	check_vsql(config_persons, "len({1, 1, 2, 2, 3, 3, None, None}) == 4")

def test_len_numberset(config_persons):
	check_vsql(config_persons, "len({1.2, 3.4, 5.6, None, 1.2, 3.4, 5.6, None}) == 4")

def test_len_strset(config_persons):
	check_vsql(config_persons, "len({'foo', 'bar', 'baz', None, 'foo', 'bar', 'baz'}) == 4")

def test_len_dateset(config_persons):
	check_vsql(config_persons, "len({@(2000-02-29), @(2000-02-29), @(2000-03-21), None}) == 3")

def test_len_datetimeset(config_persons):
	check_vsql(config_persons, "len({@(2000-02-29T12:34:56), None, @(2000-02-29T12:34:56), None, @(2000-02-29T11:22:33)}) == 3")

def test_timedelta(config_persons):
	check_vsql(config_persons, "not timedelta()")

def test_timedelta_int1(config_persons):
	check_vsql(config_persons, "timedelta(42)")

def test_timedelta_int2(config_persons):
	check_vsql(config_persons, "timedelta(42, 12)")

def test_monthdelta(config_persons):
	check_vsql(config_persons, "not monthdelta()")

def test_monthdelta_int(config_persons):
	check_vsql(config_persons, "monthdelta(42)")

def test_years(config_persons):
	check_vsql(config_persons, "years(25)")

def test_months(config_persons):
	check_vsql(config_persons, "months(3)")

def test_weeks(config_persons):
	check_vsql(config_persons, "weeks(3)")

def test_days(config_persons):
	check_vsql(config_persons, "days(12)")

def test_hours(config_persons):
	check_vsql(config_persons, "hours(8)")

def test_minutes(config_persons):
	check_vsql(config_persons, "minutes(45)")

def test_seconds(config_persons):
	check_vsql(config_persons, "seconds(60)")

def test_md5(config_persons):
	check_vsql(config_persons, "md5('gurk') == '4b5b6a3fa4af2541daa569277c7ff4c5'")

def test_random(config_persons):
	check_vsql(config_persons, "random() + 1")

def test_randrange(config_persons):
	check_vsql(config_persons, "randrange(1, 10)")

def test_seq(config_persons):
	check_vsql(config_persons, "seq()")

def test_rgb1(config_persons):
	check_vsql(config_persons, "rgb(0.2, 0.4, 0.6) == #369")

def test_rgb2(config_persons):
	check_vsql(config_persons, "rgb(0.2, 0.4, 0.6, 0.8) == #369c")

def test_list_str(config_persons):
	check_vsql(config_persons, "list('gurk') == ['g', 'u', 'r', 'k']")

def test_list_intlist(config_persons):
	check_vsql(config_persons, "list([1, 2, 3]) == [1, 2, 3]")

def test_list_numberlist(config_persons):
	check_vsql(config_persons, "list([1.2, 3.4, 5.6]) == [1.2, 3.4, 5.6]")

def test_list_strlist(config_persons):
	check_vsql(config_persons, "list(['foo', 'bar', 'baz', None]) == ['foo', 'bar', 'baz', None]")

def test_list_datelist(config_persons):
	check_vsql(config_persons, "list([@(2000-02-29), @(2000-03-01), None]) == [@(2000-02-29), @(2000-03-01), None]")

def test_list_datetimelist(config_persons):
	check_vsql(config_persons, "list([@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), None]) == [@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), None]")

def test_list_intset(config_persons):
	check_vsql(config_persons, "list({1, None}) == [1, None]")

def test_list_numberset(config_persons):
	check_vsql(config_persons, "list({1.2, None}) == [1.2, None]")

def test_list_strset(config_persons):
	check_vsql(config_persons, "list({'foo', None}) == ['foo', None]")

def test_list_dateset(config_persons):
	check_vsql(config_persons, "list({@(2000-02-29), None}) == [@(2000-02-29), None]")

def test_list_datetimeset(config_persons):
	check_vsql(config_persons, "list({@(2000-02-29T12:34:56), None}) == [@(2000-02-29T12:34:56), None]")

def test_set_str(config_persons):
	check_vsql(config_persons, "set('mississippi') == {'i', 'm', 'p', 's'}")

def test_set_intlist(config_persons):
	check_vsql(config_persons, "set([1, 2, 3, 2, 1, None]) == {1, 2, 3, None}")

def test_set_numberlist(config_persons):
	check_vsql(config_persons, "set([1.2, 3.4, 5.6, 3.4, 1.2, None]) == {1.2, 3.4, 5.6, None}")

def test_set_strlist(config_persons):
	check_vsql(config_persons, "set(['foo', 'bar', 'baz', None, 'baz', 'bar', 'foo']) == {'foo', 'bar', 'baz', None}")

def test_set_datelist(config_persons):
	check_vsql(config_persons, "set([@(2000-02-29), @(2000-03-01), None, @(2000-03-01), @(2000-02-29)]) == {@(2000-02-29), @(2000-03-01), None}")

def test_set_datetimelist(config_persons):
	check_vsql(config_persons, "set([@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), @(2000-02-29T11:22:33), None, @(2000-02-29T12:34:56)]) == {@(2000-02-29T12:34:56), @(2000-02-29T11:22:33), None}")

def test_set_intset(config_persons):
	check_vsql(config_persons, "set({1, None}) == {1, None}")

def test_set_numberset(config_persons):
	check_vsql(config_persons, "set({1.2, None}) == {1.2, None}")

def test_set_strset(config_persons):
	check_vsql(config_persons, "set({'foo', None}) == {'foo', None}")

def test_set_dateset(config_persons):
	check_vsql(config_persons, "set({@(2000-02-29), None}) == {@(2000-02-29), None}")

def test_set_datetimeset(config_persons):
	check_vsql(config_persons, "set({@(2000-02-29T12:34:56), None}) == {@(2000-02-29T12:34:56), None}")

def test_dist(config_persons):
	check_vsql(config_persons, "abs(dist(geo(49.95, 11.59, 'Here'), geo(12.34, 56.67, 'There')) - 5845.77551787602) < 1e-5")

def test_abs(config_persons):
	check_vsql(config_persons, "abs(-42) == 42")

def test_cos_bool(config_persons):
	check_vsql(config_persons, "cos(False) == 1")

def test_cos_int(config_persons):
	check_vsql(config_persons, "cos(0) == 1")

def test_cos_number1(config_persons):
	check_vsql(config_persons, "cos(0.0) == 1")

def test_cos_number2(config_persons):
	check_vsql(config_persons, f"abs(cos({math.pi} / 2)) < 1e-10")

def test_cos_number3(config_persons):
	check_vsql(config_persons, f"abs(cos({math.pi}) + 1) < 1e-10")

def test_sin_bool(config_persons):
	check_vsql(config_persons, "sin(False) == 0")

def test_sin_int(config_persons):
	check_vsql(config_persons, "sin(0) == 0")

def test_sin_number1(config_persons):
	check_vsql(config_persons, "sin(0.0) == 0")

def test_sin_number2(config_persons):
	check_vsql(config_persons, f"abs(sin({math.pi} / 2) - 1) < 1e-10")

def test_sin_number3(config_persons):
	check_vsql(config_persons, f"abs(sin({math.pi})) < 1e-10")

def test_tan_bool(config_persons):
	check_vsql(config_persons, "tan(False) == 0")

def test_tan_int(config_persons):
	check_vsql(config_persons, "tan(0) == 0")

def test_tan_number1(config_persons):
	check_vsql(config_persons, "tan(0.0) == 0")

def test_tan_number2(config_persons):
	check_vsql(config_persons, f"abs(tan(0.25 * {math.pi}) - 1) < 1e-10")

def test_tan_number3(config_persons):
	check_vsql(config_persons, f"abs(tan(0.75 * {math.pi}) + 1) < 1e-10")

def test_sqrt_bool1(config_persons):
	check_vsql(config_persons, "sqrt(False) == 0.0")

def test_sqrt_bool2(config_persons):
	check_vsql(config_persons, "sqrt(True) == 1.0")

def test_sqrt_int1(config_persons):
	check_vsql(config_persons, "sqrt(16) == 4.0")

def test_sqrt_int2(config_persons):
	check_vsql(config_persons, "sqrt(-16) is None")

def test_sqrt_number1(config_persons):
	check_vsql(config_persons, "sqrt(16.0) == 4.0")

def test_sqrt_number2(config_persons):
	check_vsql(config_persons, "sqrt(-16.0) is None")
