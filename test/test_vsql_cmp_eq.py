"""
Tests for the vSQL equality comparision operator ``==``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_none_false(config_data):
	check_vsql(config_data, "app.p_bool_none.value == None")

def test_bool_none_true(config_data):
	check_vsql(config_data, "not (app.p_bool_true.value == None)")

def test_int_none_false(config_data):
	check_vsql(config_data, "app.p_int_none.value == None")

def test_int_none_true(config_data):
	check_vsql(config_data, "not (app.p_int_value.value == None)")

def test_number_none_false(config_data):
	check_vsql(config_data, "app.p_number_none.value == None")

def test_number_none_true(config_data):
	check_vsql(config_data, "not (app.p_number_value.value == None)")

def test_str_none_false(config_data):
	check_vsql(config_data, "app.p_str_none.value == None")

def test_str_none_true(config_data):
	check_vsql(config_data, "not (app.p_str_value.value == None)")

def test_date_none_false(config_data):
	check_vsql(config_data, "app.p_date_none.value == None")

def test_date_none_true(config_data):
	check_vsql(config_data, "not (app.p_date_value.value == None)")

def test_datetime_none_false(config_data):
	check_vsql(config_data, "app.p_datetime_none.value == None")

def test_datetime_none_true(config_data):
	check_vsql(config_data, "not (app.p_datetime_value.value == None)")

def test_color_none_false(config_data):
	check_vsql(config_data, "app.p_color_none.value == None")

def test_color_none_true(config_data):
	check_vsql(config_data, "not (app.p_color_value.value == None)")

def test_datedelta_none_false(config_data):
	check_vsql(config_data, "app.p_datedelta_none.value == None")

def test_datedelta_none_true(config_data):
	check_vsql(config_data, "not (app.p_datedelta_value.value == None)")

def test_datetimedelta_none_false(config_data):
	check_vsql(config_data, "app.p_datetimedelta_none.value == None")

def test_datetimedelta_none_true(config_data):
	check_vsql(config_data, "not (app.p_datetimedelta_value.value == None)")

def test_monthdelta_none_false(config_data):
	check_vsql(config_data, "app.p_monthdelta_none.value == None")

def test_monthdelta_none_true(config_data):
	check_vsql(config_data, "not (app.p_monthdelta_value.value == None)")

def test_bool_bool_false(config_data):
	check_vsql(config_data, "app.p_bool_false.value == False")

def test_bool_bool_true(config_data):
	check_vsql(config_data, "app.p_bool_true.value == True")

def test_bool_int_false(config_data):
	check_vsql(config_data, "app.p_bool_false.value == 0")

def test_bool_int_true(config_data):
	check_vsql(config_data, "app.p_bool_true.value == 1")

def test_int_bool_false(config_data):
	check_vsql(config_data, "0 == app.p_bool_false.value")

def test_int_bool_true(config_data):
	check_vsql(config_data, "1 == app.p_bool_true.value")

def test_number_bool_false(config_data):
	check_vsql(config_data, "0.0 == app.p_bool_false.value")

def test_number_bool_true(config_data):
	check_vsql(config_data, "1.0 == app.p_bool_true.value")

def test_number_int_false(config_data):
	check_vsql(config_data, "not (42.5 == app.p_int_value.value)")

def test_number_int_true(config_data):
	check_vsql(config_data, "1777.0 == app.p_int_value.value")

def test_number_number_false(config_data):
	check_vsql(config_data, "not (17.23 == app.p_number_value.value)")

def test_number_number_true(config_data):
	check_vsql(config_data, "42.5 == app.p_number_value.value")

def test_str_str_false(config_data):
	check_vsql(config_data, "not (app.p_str_none.value == 'gurk')")

def test_str_str_true(config_data):
	check_vsql(config_data, "app.p_str_value.value == 'gurk'")

def test_date_date_false(config_data):
	check_vsql(config_data, "not (app.p_date_none.value == @(2000-02-29))")

def test_date_date_true(config_data):
	check_vsql(config_data, "app.p_date_value.value == @(2000-02-29)")

def test_datetime_datetime_false(config_data):
	check_vsql(config_data, "not (app.p_datetime_none.value == @(2000-02-29T12:34:56))")

def test_datetime_datetime_true(config_data):
	check_vsql(config_data, "app.p_datetime_value.value == @(2000-02-29T12:34:56)")

def test_datedelta_datedelta_false(config_data):
	check_vsql(config_data, "not (app.p_datedelta_none.value == days(12))")

def test_datedelta_datedelta_true(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value == days(12)")

def test_color_color_false(config_data):
	check_vsql(config_data, "not (app.p_color_none.value == #369c)")

def test_color_color_true(config_data):
	check_vsql(config_data, "app.p_color_value.value == #369c")

def test_datetimedelta_datetimedelta_false(config_data):
	check_vsql(config_data, "not (app.p_datetimedelta_none.value == timedelta(1, 45296))")

def test_datetimedelta_datetimedelta_true(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value == timedelta(1, 45296)")

def test_intlist_intlist1(config_data):
	check_vsql(config_data, "not ([1] == [2])")

def test_intlist_intlist2(config_data):
	check_vsql(config_data, "not ([1] == [1, 2])")

def test_intlist_intlist3(config_data):
	check_vsql(config_data, "not ([1, 2] == [1])")

def test_intlist_intlist4(config_data):
	check_vsql(config_data, "not ([1, None] == [1])")

def test_intlist_intlist5(config_data):
	check_vsql(config_data, "[1, None, 2, None, 3] == [1, None, 2, None, 3]")

def test_intlist_numberlist1(config_data):
	check_vsql(config_data, "not ([1] == [1.5])")

def test_intlist_numberlist2(config_data):
	check_vsql(config_data, "not ([1] == [1.0, 2.0])")

def test_intlist_numberlist3(config_data):
	check_vsql(config_data, "not ([1, 2] == [1.0])")

def test_intlist_numberlist4(config_data):
	check_vsql(config_data, "not ([1, None] == [1.0])")

def test_intlist_numberlist5(config_data):
	check_vsql(config_data, "[1, None, 2, None, 3] == [1.0, None, 2.0, None, 3.0]")

def test_numberlist_intlist1(config_data):
	check_vsql(config_data, "not ([1.5] == [2])")

def test_numberlist_intlist2(config_data):
	check_vsql(config_data, "not ([1.0] == [1, 2])")

def test_numberlist_intlist3(config_data):
	check_vsql(config_data, "not ([1.0, 2.0] == [1])")

def test_numberlist_intlist4(config_data):
	check_vsql(config_data, "not ([1.0, None] == [1])")

def test_numberlist_intlist5(config_data):
	check_vsql(config_data, "[1.0, None, 2.0, None, 3.0] == [1, None, 2, None, 3]")

def test_numberlist_numberlist1(config_data):
	check_vsql(config_data, "not ([1.5] == [2.5])")

def test_numberlist_numberlist2(config_data):
	check_vsql(config_data, "not ([1.0] == [1.0, 2.0])")

def test_numberlist_numberlist3(config_data):
	check_vsql(config_data, "not ([1.0, 2.0] == [1.0])")

def test_numberlist_numberlist4(config_data):
	check_vsql(config_data, "not ([1.5, None] == [1.5])")

def test_numberlist_numberlist5(config_data):
	check_vsql(config_data, "[1.5, None, 2.5, None, 3.5] == [1.5, None, 2.5, None, 3.5]")

def test_strlist_strlist1(config_data):
	check_vsql(config_data, "not (['foo'] == ['bar'])")

def test_strlist_strlist2(config_data):
	check_vsql(config_data, "not (['foo'] == ['foo', 'bar'])")

def test_strlist_strlist3(config_data):
	check_vsql(config_data, "not (['foo', 'bar'] == ['foo'])")

def test_strlist_strlist4(config_data):
	check_vsql(config_data, "not (['foo', None] == ['foo'])")

def test_strlist_strlist5(config_data):
	check_vsql(config_data, "['foo', None, 'bar', None, 'baz'] == ['foo', None, 'bar', None, 'baz']")

def test_datelist_datelist1(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] == [@(2000-03-01)])")

def test_datelist_datelist2(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] == [@(2000-02-29), @(2000-03-01)])")

def test_datelist_datelist3(config_data):
	check_vsql(config_data, "not ([@(2000-02-29), @(2000-03-01)] == [@(2000-02-29)])")

def test_datelist_datelist4(config_data):
	check_vsql(config_data, "not ([@(2000-02-29), None] == [@(2000-02-29)])")

def test_datelist_datelist5(config_data):
	check_vsql(config_data, "[@(2000-02-29), None, @(2000-03-01), None, @(2000-03-02)] == [@(2000-02-29), None, @(2000-03-01), None, @(2000-03-02)]")

def test_datetimelist_datetimelist1(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] == [@(2000-03-01T12:34:56)])")

def test_datetimelist_datetimelist2(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] == [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)])")

def test_datetimelist_datetimelist3(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)] == [@(2000-02-29T12:34:56)])")

def test_datetimelist_datetimelist4(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56), None] == [@(2000-02-29T12:34:56)])")

def test_datetimelist_datetimelist5(config_data):
	check_vsql(config_data, "[@(2000-02-29T12:34:56), None, @(2000-03-01T12:34:56), None, @(2000-03-02T12:34:56)] == [@(2000-02-29T12:34:56), None, @(2000-03-01T12:34:56), None, @(2000-03-02T12:34:56)]")

def test_nulllist_nulllist1(config_data):
	check_vsql(config_data, "[] == []")

def test_nulllist_nulllist2(config_data):
	check_vsql(config_data, "[None, None] == [None, None]")

def test_nulllist_nulllist3(config_data):
	check_vsql(config_data, "not ([None] == [None, None])")

def test_nulllist_intlist1(config_data):
	check_vsql(config_data, "not ([] == [1])")

def test_nulllist_intlist2(config_data):
	check_vsql(config_data, "not ([None] == [1])")

def test_nulllist_intlist3(config_data):
	check_vsql(config_data, "not ([None, None] == [1])")

def test_nulllist_numberlist1(config_data):
	check_vsql(config_data, "not ([] == [1.1])")

def test_nulllist_numberlist2(config_data):
	check_vsql(config_data, "not ([None] == [1.1])")

def test_nulllist_numberlist3(config_data):
	check_vsql(config_data, "not ([None, None] == [1.1])")

def test_nulllist_strlist1(config_data):
	check_vsql(config_data, "not ([] == ['gurk'])")

def test_nulllist_strlist2(config_data):
	check_vsql(config_data, "not ([None] == ['gurk'])")

def test_nulllist_strlist3(config_data):
	check_vsql(config_data, "not ([None, None] == ['gurk'])")

def test_nulllist_datelist1(config_data):
	check_vsql(config_data, "not ([] == [@(2000-02-29)])")

def test_nulllist_datelist2(config_data):
	check_vsql(config_data, "not ([None] == [@(2000-02-29)])")

def test_nulllist_datelist3(config_data):
	check_vsql(config_data, "not ([None, None] == [@(2000-02-29)])")

def test_nulllist_datetimelist1(config_data):
	check_vsql(config_data, "not ([] == [@(2000-02-29T12:34:56)])")

def test_nulllist_datetimelist2(config_data):
	check_vsql(config_data, "not ([None] == [@(2000-02-29T12:34:56)])")

def test_nulllist_datetimelist3(config_data):
	check_vsql(config_data, "not ([None, None] == [@(2000-02-29T12:34:56)])")

def test_intlist_nulllist1(config_data):
	check_vsql(config_data, "not ([1] == [])")

def test_intlist_nulllist2(config_data):
	check_vsql(config_data, "not ([1] == [None])")

def test_intlist_nulllist3(config_data):
	check_vsql(config_data, "not ([1] == [None, None])")

def test_numberlist_nulllist1(config_data):
	check_vsql(config_data, "not ([1.1] == [])")

def test_numberlist_nulllist2(config_data):
	check_vsql(config_data, "not ([1.1] == [None])")

def test_numberlist_nulllist3(config_data):
	check_vsql(config_data, "not ([1.1] == [None, None])")

def test_strlist_nulllist1(config_data):
	check_vsql(config_data, "not (['gurk'] == [])")

def test_strlist_nulllist2(config_data):
	check_vsql(config_data, "not (['gurk'] == [None])")

def test_strlist_nulllist3(config_data):
	check_vsql(config_data, "not (['gurk'] == [None, None])")

def test_datelist_nulllist1(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] == [])")

def test_datelist_nulllist2(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] == [None])")

def test_datelist_nulllist3(config_data):
	check_vsql(config_data, "not ([@(2000-02-29)] == [None, None])")

def test_datetimelist_nulllist1(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] == [])")

def test_datetimelist_nulllist2(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] == [None])")

def test_datetimelist_nulllist3(config_data):
	check_vsql(config_data, "not ([@(2000-02-29T12:34:56)] == [None, None])")

def test_intset_intset1(config_data):
	check_vsql(config_data, "not ({1} == {2})")

def test_intset_intset2(config_data):
	check_vsql(config_data, "not ({1} == {1, 2})")

def test_intset_intset3(config_data):
	check_vsql(config_data, "not ({1, 2} == {1})")

def test_intset_intset4(config_data):
	check_vsql(config_data, "({1, 2} == {2, 1})")

def test_intset_intset5(config_data):
	check_vsql(config_data, "not ({1, None} == {1})")

def test_intset_intset6(config_data):
	check_vsql(config_data, "{1, None, 2, None, 3} == {None, 3, 2, 1, None}")

def test_numberset_numberset1(config_data):
	check_vsql(config_data, "not ({1.5} == {2.5})")

def test_numberset_numberset2(config_data):
	check_vsql(config_data, "not ({1.5} == {1.5, 2.5})")

def test_numberset_numberset3(config_data):
	check_vsql(config_data, "not ({1.5, 2.5} == {1.5})")

def test_numberset_numberset4(config_data):
	check_vsql(config_data, "({1.5, 2.5} == {2.5, 1.5})")

def test_numberset_numberset5(config_data):
	check_vsql(config_data, "not ({1.5, None} == {1.5})")

def test_numberset_numberset6(config_data):
	check_vsql(config_data, "{1.5, None, 2.5, None, 3.5} == {None, 3.5, 2.5, 1.5, None}")

def test_strset_strset1(config_data):
	check_vsql(config_data, "not ({1.5} == {2.5})")

def test_strset_strset2(config_data):
	check_vsql(config_data, "not ({'foo'} == {'foo', 'bar'})")

def test_strset_strset3(config_data):
	check_vsql(config_data, "not ({'foo', 'bar'} == {'foo'})")

def test_strset_strset4(config_data):
	check_vsql(config_data, "{'foo', 'bar'} == {'bar', 'foo'}")

def test_strset_strset5(config_data):
	check_vsql(config_data, "not ({'foo', None} == {'foo'})")

def test_strset_strset6(config_data):
	check_vsql(config_data, "{'foo', None, 'bar', None, 'baz'} == {None, 'baz', 'bar', 'foo', None}")

def test_dateset_dateset1(config_data):
	check_vsql(config_data, "not ({@(2000-02-29)} == {@(2000-03-01)})")

def test_dateset_dateset2(config_data):
	check_vsql(config_data, "not ({@(2000-02-29)} == {@(2000-02-29), @(2000-03-01)})")

def test_dateset_dateset3(config_data):
	check_vsql(config_data, "not ({@(2000-02-29), @(2000-03-01)} == {@(2000-02-29)})")

def test_dateset_dateset4(config_data):
	check_vsql(config_data, "{@(2000-02-29), @(2000-03-01)} == {@(2000-03-01), @(2000-02-29)}")

def test_dateset_dateset5(config_data):
	check_vsql(config_data, "not ({@(2000-02-29), None} == {@(2000-02-29)})")

def test_dateset_dateset6(config_data):
	check_vsql(config_data, "{@(2000-02-29), None, @(2000-03-01), None, @(2000-03-02)} == {None, @(2000-03-02), @(2000-03-01), @(2000-02-29), None}")

def test_datetimeset_datetimeset1(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56)} == {@(2000-03-01T12:34:56)})")

def test_datetimeset_datetimeset2(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56)} == {@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)})")

def test_datetimeset_datetimeset3(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)} == {@(2000-02-29T12:34:56)})")

def test_datetimeset_datetimeset4(config_data):
	check_vsql(config_data, "{@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)} == {@(2000-03-01T12:34:56), @(2000-02-29T12:34:56)}")

def test_datetimeset_datetimeset5(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56), None} == {@(2000-02-29T12:34:56)})")

def test_datetimeset_datetimeset6(config_data):
	check_vsql(config_data, "{@(2000-02-29T12:34:56), None, @(2000-03-01T12:34:56), None, @(2000-03-02T12:34:56)} == {None, @(2000-03-02T12:34:56), @(2000-03-01T12:34:56), @(2000-02-29T12:34:56), None}")

def test_nullset_nullset1(config_data):
	check_vsql(config_data, "{/} == {/}")

def test_nullset_nullset2(config_data):
	check_vsql(config_data, "{None} == {None}")

def test_nullset_nullset3(config_data):
	check_vsql(config_data, "{None} == {None, None}")

def test_nullset_nullset4(config_data):
	check_vsql(config_data, "not ({/} == {None, None})")

def test_nullset_intset1(config_data):
	check_vsql(config_data, "not ({/} == {1})")

def test_nullset_intset2(config_data):
	check_vsql(config_data, "not ({None} == {1})")

def test_nullset_intset3(config_data):
	check_vsql(config_data, "not ({None, None} == {1})")

def test_nullset_intset4(config_data):
	check_vsql(config_data, "not ({None, None} == {1, 2})")

def test_nullset_numberset1(config_data):
	check_vsql(config_data, "not ({/} == {1.1})")

def test_nullset_numberset2(config_data):
	check_vsql(config_data, "not ({None} == {1.1})")

def test_nullset_numberset3(config_data):
	check_vsql(config_data, "not ({None, None} == {1.1})")

def test_nullset_numberset4(config_data):
	check_vsql(config_data, "not ({None, None} == {1.1, 2.2})")

def test_nullset_strset1(config_data):
	check_vsql(config_data, "not ({/} == {'gurk'})")

def test_nullset_strset2(config_data):
	check_vsql(config_data, "not ({None} == {'gurk'})")

def test_nullset_strset3(config_data):
	check_vsql(config_data, "not ({None, None} == {'gurk'})")

def test_nullset_strset4(config_data):
	check_vsql(config_data, "not ({None, None} == {'gurk', 'hurz'})")

def test_nullset_dateset1(config_data):
	check_vsql(config_data, "not ({/} == {@(2000-02-29)})")

def test_nullset_dateset2(config_data):
	check_vsql(config_data, "not ({None} == {@(2000-02-29)})")

def test_nullset_dateset3(config_data):
	check_vsql(config_data, "not ({None, None} == {@(2000-02-29)})")

def test_nullset_dateset4(config_data):
	check_vsql(config_data, "not ({None, None} == {@(2000-02-29), @(2000-03-01)})")

def test_nullset_datetimeset1(config_data):
	check_vsql(config_data, "not ({/} == {@(2000-02-29T12:34:56)})")

def test_nullset_datetimeset2(config_data):
	check_vsql(config_data, "not ({None} == {@(2000-02-29T12:34:56)})")

def test_nullset_datetimeset3(config_data):
	check_vsql(config_data, "not ({None, None} == {@(2000-02-29T12:34:56)})")

def test_nullset_datetimeset4(config_data):
	check_vsql(config_data, "not ({None, None} == {@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)})")

def test_intset_nullset1(config_data):
	check_vsql(config_data, "not ({1} == {/})")

def test_intset_nullset2(config_data):
	check_vsql(config_data, "not ({1} == {None})")

def test_intset_nullset3(config_data):
	check_vsql(config_data, "not ({1} == {None, None})")

def test_intset_nullset4(config_data):
	check_vsql(config_data, "not ({1, 2} == {None, None})")

def test_numberset_nullset1(config_data):
	check_vsql(config_data, "not ({1.1} == {/})")

def test_numberset_nullset2(config_data):
	check_vsql(config_data, "not ({1.1} == {None})")

def test_numberset_nullset3(config_data):
	check_vsql(config_data, "not ({1.1} == {None, None})")

def test_numberset_nullset4(config_data):
	check_vsql(config_data, "not ({1.1, 2.2} == {None, None})")

def test_strset_nullset1(config_data):
	check_vsql(config_data, "not ({'gurk'} == {/})")

def test_strset_nullset2(config_data):
	check_vsql(config_data, "not ({'gurk'} == {None})")

def test_strset_nullset3(config_data):
	check_vsql(config_data, "not ({'gurk'} == {None, None})")

def test_strset_nullset4(config_data):
	check_vsql(config_data, "not ({'gurk', 'hurz'} == {None, None})")

def test_dateset_nullset1(config_data):
	check_vsql(config_data, "not ({@(2000-02-29)} == {/})")

def test_dateset_nullset2(config_data):
	check_vsql(config_data, "not ({@(2000-02-29)} == {None})")

def test_dateset_nullset3(config_data):
	check_vsql(config_data, "not ({@(2000-02-29)} == {None, None})")

def test_dateset_nullset4(config_data):
	check_vsql(config_data, "not ({@(2000-02-29), @(2000-03-01)} == {None, None})")

def test_datetimeset_nullset1(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56)} == {/})")

def test_datetimeset_nullset2(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56)} == {None})")

def test_datetimeset_nullset3(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56)} == {None, None})")

def test_datetimeset_nullset4(config_data):
	check_vsql(config_data, "not ({@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)} == {None, None})")

# FIXME Add tests for mixed type comparisons?
