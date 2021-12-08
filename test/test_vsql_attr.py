"""
Tests for vSQL attributes.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_date_year(config_persons):
	check_vsql(config_persons, "@(2000-02-29).year == 2000")

def test_datetime_year(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).year == 2000")

def test_date_month(config_persons):
	check_vsql(config_persons, "@(2000-02-29).month == 2")

def test_datetime_month(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).month == 2")

def test_date_day(config_persons):
	check_vsql(config_persons, "@(2000-02-29).day == 29")

def test_datetime_day(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).day == 29")

def test_datetime_hour(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).hour == 12")

def test_datetime_minute(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).minute == 34")

def test_datetime_second(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).second == 56")

def test_date_weekday(config_persons):
	check_vsql(config_persons, "@(2000-02-29).weekday == 1")

def test_datetime_weekday(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).weekday == 1")

def test_date_yearday(config_persons):
	check_vsql(config_persons, "@(2000-02-29).yearday == 60")

def test_datetime_yearday(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).yearday == 60")

def test_datedelta_days(config_persons):
	check_vsql(config_persons, "days(12).days == 12")

def test_datetimedelta_days(config_persons):
	check_vsql(config_persons, "timedelta(12, 34).days == 12")

def test_datetimedelta_seconds(config_persons):
	check_vsql(config_persons, "timedelta(12, 34).seconds == 34")

def test_datetimedelta_total_days(config_persons):
	check_vsql(config_persons, "timedelta(12, 34).total_days * 60 * 60 * 24 == 12 * 60 * 60 * 24 + 34")

def test_datetimedelta_total_hours(config_persons):
	check_vsql(config_persons, "timedelta(12, 34).total_hours * 60 * 60 == 12 * 60 * 60 * 24 + 34")

def test_datetimedelta_total_minutes(config_persons):
	check_vsql(config_persons, "timedelta(12, 34).total_minutes * 60 == 12 * 60 * 60 * 24 + 34")

def test_datetimedelta_total_seconds(config_persons):
	check_vsql(config_persons, "timedelta(12, 34).total_seconds == 12 * 60 * 60 * 24 + 34")

def test_color_r(config_persons):
	check_vsql(config_persons, "app.p_color_value.value.r == 0x33")

def test_color_g(config_persons):
	check_vsql(config_persons, "app.p_color_value.value.g == 0x66")

def test_color_b(config_persons):
	check_vsql(config_persons, "app.p_color_value.value.b == 0x99")

def test_color_a(config_persons):
	check_vsql(config_persons, "app.p_color_value.value.a == 0xcc")

def test_geo_lat(config_persons):
	check_vsql(config_persons, "geo(49.95, 11.59, 'Here').lat == 49.95")

def test_geo_long(config_persons):
	check_vsql(config_persons, "geo(49.95, 11.59, 'Here').long == 11.59")

def test_geo_info_with_info(config_persons):
	check_vsql(config_persons, "geo(49.95, 11.59, 'Here').info == 'Here'")

def test_geo_info_without_info(config_persons):
	check_vsql(config_persons, "geo(49.95, 11.59).info is None")
