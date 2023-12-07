"""
Tests for the vSQL binary containment test operator ``in``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

d1 = "@(2000-02-29)"

dt1 = "@(2000-02-29T12:34:56)"

def test_null_intlist1(config_data):
	check_vsql(config_data, "not (None in [1, 2])")

def test_null_intlist2(config_data):
	check_vsql(config_data, "None in [1, None, 2]")

def test_null_numberlist1(config_data):
	check_vsql(config_data, "not (None in [1.1, 2.2])")

def test_null_numberlist2(config_data):
	check_vsql(config_data, "None in [1.1, None, 2.2]")

def test_null_strlist1(config_data):
	check_vsql(config_data, "not (None in ['foo', 'bar'])")

def test_null_strlist2(config_data):
	check_vsql(config_data, "None in ['foo', None, 'bar']")

def test_null_datelist1(config_data):
	check_vsql(config_data, "not (None in [@(2000-02-29), @(2000-03-01)])")

def test_null_datelist2(config_data):
	check_vsql(config_data, "None in [@(2000-02-29), None, @(2000-03-01)]")

def test_null_datetimelist1(config_data):
	check_vsql(config_data, "not (None in [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)])")

def test_null_datetimelist2(config_data):
	check_vsql(config_data, "None in [@(2000-02-29T12:34:56), None, @(2000-03-01T12:34:56)]")

def test_str_str1(config_data):
	check_vsql(config_data, "not ('az' in app.p_str_value.value)")

def test_str_str2(config_data):
	check_vsql(config_data, "'ur' in app.p_str_value.value")

def test_str_strlist1(config_data):
	check_vsql(config_data, "not ('hinz' in ['gurk', 'hurz'])")

def test_str_strlist2(config_data):
	check_vsql(config_data, "'hurz' in ['gurk', 'hurz']")

def test_str_strset1(config_data):
	check_vsql(config_data, "not ('hinz' in {'gurk', 'hurz'})")

def test_str_strset2(config_data):
	check_vsql(config_data, "'hurz' in {'gurk', 'hurz'}")

def test_int_intlist1(config_data):
	check_vsql(config_data, "not (1 in [2, 3])")

def test_int_intlist2(config_data):
	check_vsql(config_data, "3 in [1, 2, 3]")

def test_int_numberlist1(config_data):
	check_vsql(config_data, "not (1 in [2.2, 3.3])")

def test_int_numberlist2(config_data):
	check_vsql(config_data, "3 in [1.1, 2.2, 3.0]")

def test_int_intset1(config_data):
	check_vsql(config_data, "not (1 in {2, 3})")

def test_int_intset2(config_data):
	check_vsql(config_data, "3 in {1, 2, 3}")

def test_int_numberset1(config_data):
	check_vsql(config_data, "not (1 in {2.2, 3.3})")

def test_int_numberset2(config_data):
	check_vsql(config_data, "3 in {1.1, 2.2, 3.0}")

def test_number_intlist1(config_data):
	check_vsql(config_data, "not (1.0 in [2, 3])")

def test_number_intlist2(config_data):
	check_vsql(config_data, "3.0 in [1, 2, 3]")

def test_number_numberlist1(config_data):
	check_vsql(config_data, "not (1.0 in [2.2, 3.3])")

def test_number_numberlist2(config_data):
	check_vsql(config_data, "3.0 in [1.1, 2.2, 3.0]")

def test_number_intset1(config_data):
	check_vsql(config_data, "not (1.0 in {2, 3})")

def test_number_intset2(config_data):
	check_vsql(config_data, "3.0 in {1, 2, 3}")

def test_number_numberset1(config_data):
	check_vsql(config_data, "not (1.0 in {2.2, 3.3})")

def test_number_numberset2(config_data):
	check_vsql(config_data, "3.3 in {1.1, 2.2, 3.3}")

def test_date_datelist1(config_data):
	check_vsql(config_data, "not (@(2000-02-29) in [@(2000-02-28), @(2000-03-01)])")

def test_date_datelist2(config_data):
	check_vsql(config_data, "@(2000-02-29) in [@(2000-02-29), @(2000-03-01)]")

def test_date_dateset1(config_data):
	check_vsql(config_data, "not (@(2000-02-29) in {@(2000-02-28), @(2000-03-01)})")

def test_date_dateset2(config_data):
	check_vsql(config_data, "@(2000-02-29) in {@(2000-02-29), @(2000-03-01)}")

def test_datetime_datetimelist1(config_data):
	check_vsql(config_data, "not (@(2000-02-29T12:34:56) in [@(2000-02-28T12:34:56), @(2000-03-01T12:34:56)])")

def test_datetime_datetimelist2(config_data):
	check_vsql(config_data, "@(2000-02-29T12:34:56) in [@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)]")

def test_datetime_datetimeset1(config_data):
	check_vsql(config_data, "not (@(2000-02-29T12:34:56) in {@(2000-02-28T12:34:56), @(2000-03-01T12:34:56)})")

def test_datetime_datetimeset2(config_data):
	check_vsql(config_data, "@(2000-02-29T12:34:56) in {@(2000-02-29T12:34:56), @(2000-03-01T12:34:56)}")

def test_null_nulllist1(config_data):
	check_vsql(config_data, "not (None in [])")

def test_null_nulllist2(config_data):
	check_vsql(config_data, "None in [None, None]")

def test_int_nulllist1(config_data):
	check_vsql(config_data, "not ([None, 1][0] in [])")

def test_int_nulllist2(config_data):
	check_vsql(config_data, "[None, 1][0] in [None]")

def test_int_nulllist3(config_data):
	check_vsql(config_data, "not (1 in [None])")

def test_number_nulllist1(config_data):
	check_vsql(config_data, "not ([None, 1.1][0] in [])")

def test_number_nulllist2(config_data):
	check_vsql(config_data, "[None, 1.1][0] in [None]")

def test_number_nulllist3(config_data):
	check_vsql(config_data, "not (1.1 in [None])")

def test_str_nulllist1(config_data):
	check_vsql(config_data, "not ([None, 'gurk'][0] in [])")

def test_str_nulllist2(config_data):
	check_vsql(config_data, "[None, 'gurk'][0] in [None]")

def test_str_nulllist3(config_data):
	check_vsql(config_data, "not ('gurk' in [None])")

def test_date_nulllist1(config_data):
	check_vsql(config_data, f"not ([None, {d1}][0] in [])")

def test_date_nulllist2(config_data):
	check_vsql(config_data, f"[None, {d1}][0] in [None]")

def test_date_nulllist3(config_data):
	check_vsql(config_data, f"not ({d1} in [None])")

def test_datetime_nulllist1(config_data):
	check_vsql(config_data, f"not ([None, {dt1}][0] in [])")

def test_datetime_nulllist2(config_data):
	check_vsql(config_data, f"[None, {dt1}][0] in [None]")

def test_datetime_nulllist3(config_data):
	check_vsql(config_data, f"not ({dt1} in [None])")
