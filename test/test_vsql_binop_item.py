"""
Tests for the vSQL binary item access operator ``A[B]``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_str_bool(config_persons):
	check_vsql(config_persons, "app.p_str_value.value[True] == 'u'")

def test_str_int(config_persons):
	check_vsql(config_persons, "app.p_str_value.value[2] == 'r'")

def test_strlist_bool(config_persons):
	check_vsql(config_persons, "['gurk', 'hurz', 'hinz', 'kunz'][True] == 'hurz'")

def test_strlist_int(config_persons):
	check_vsql(config_persons, "['gurk', 'hurz', 'hinz', 'kunz'][2] == 'hinz'")

def test_intlist_bool(config_persons):
	check_vsql(config_persons, "[1, 2, 3][True] == 2")

def test_intlist_int(config_persons):
	check_vsql(config_persons, "[1, 2, 3][2] == 3")

def test_numberlist_bool(config_persons):
	check_vsql(config_persons, "[1.1, 2.2, 3.3][True] == 2.2")

def test_numberlist_int(config_persons):
	check_vsql(config_persons, "[1.1, 2.2, 3.3][2] == 3.3")

def test_datelist_bool(config_persons):
	check_vsql(config_persons, "[@(2000-02-29), @(2000-03-01), @(2000-03-02)][True] == @(2000-03-01)")

def test_datelist_int(config_persons):
	check_vsql(config_persons, "[@(2000-02-29), @(2000-03-01), @(2000-03-02)][2] == @(2000-03-02)")

def test_datetimelist_bool(config_persons):
	check_vsql(config_persons, "[@(2000-02-29T12:34:56), @(2000-03-01T12:34:56), @(2000-03-02T12:34:56)][True] == @(2000-03-01T12:34:56)")

def test_datetimelist_int(config_persons):
	check_vsql(config_persons, "[@(2000-02-29T12:34:56), @(2000-03-01T12:34:56), @(2000-03-02T12:34:56)][2] == @(2000-03-02T12:34:56)")

def test_nulllist_bool1(config_persons):
	check_vsql(config_persons, "[][False] is None")

def test_nulllist_bool2(config_persons):
	check_vsql(config_persons, "[None, None][True] is None")

def test_nulllist_int1(config_persons):
	check_vsql(config_persons, "[][0] is None")

def test_nulllist_int2(config_persons):
	check_vsql(config_persons, "[None, None][1] is None")

