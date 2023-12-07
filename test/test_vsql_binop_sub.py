"""
Tests for the vSQL subtraction operator ``-``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool_bool1(config_data):
	check_vsql(config_data, "app.p_bool_none.value - True is None")

def test_bool_bool2(config_data):
	check_vsql(config_data, "app.p_bool_false.value - True == -1")

def test_bool_bool3(config_data):
	check_vsql(config_data, "app.p_bool_true.value - True == 0")

def test_bool_int(config_data):
	check_vsql(config_data, "app.p_bool_true.value - 1 == 0")

def test_bool_number(config_data):
	check_vsql(config_data, "app.p_bool_true.value - 1.5 == -0.5")

def test_int_bool(config_data):
	check_vsql(config_data, "1 - app.p_bool_true.value == 0")

def test_int_int(config_data):
	check_vsql(config_data, "1 - app.p_int_value.value == -1776")

def test_int_number(config_data):
	check_vsql(config_data, "1 - app.p_number_value.value == -41.5")

def test_number_bool(config_data):
	check_vsql(config_data, "app.p_number_value.value - app.p_bool_true.value == 41.5")

def test_number_int(config_data):
	check_vsql(config_data, "app.p_number_value.value - 1 == 41.5")

def test_number_number(config_data):
	check_vsql(config_data, "app.p_number_value.value - 1.5 == 41.0")

def test_date_datedelta(config_data):
	check_vsql(config_data, "app.p_date_value.value - days(1) == @(2000-02-28)")

def test_date_date(config_data):
	check_vsql(config_data, "@(2000-03-01) - app.p_date_value.value == days(1)")

def test_datetime_datetime(config_data):
	check_vsql(config_data, "@(2000-03-01T13:35:57) - app.p_datetime_value.value == timedelta(1, ((1 * 60 + 1) * 60) + 1)")

def test_date_monthdelta(config_data):
	check_vsql(config_data, "@(2000-03-31) - months(1) == app.p_date_value.value")

def test_datetime_monthdelta(config_data):
	check_vsql(config_data, "@(2000-03-31T12:34:56) - months(1) == app.p_datetime_value.value")

def test_datedelta_datedelta(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value - days(7) == days(5)")

def test_monthdelta_monthdelta(config_data):
	check_vsql(config_data, "app.p_monthdelta_value.value - months(12) == months(-9)")

def test_datedelta_datetimedelta(config_data):
	check_vsql(config_data, "app.p_datedelta_value.value - hours(12) == timedelta(11, 12 * 60 * 60)")

def test_datetimedelta_datedelta(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value - days(1) == timedelta(0, (12 * 60 + 34) * 60 + 56)")

def test_datetimedelta_datetimedelta(config_data):
	check_vsql(config_data, "app.p_datetimedelta_value.value - timedelta(1, (12 * 60 + 34) * 60 + 56) == timedelta(0, 0)")

