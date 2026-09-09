# -*- coding:utf-8 -*-
"""실제 코레일 서버와 통신하는 통합 테스트.

기본적으로는 전부 skip 된다. 돌리려면 실제 계정이 필요하다.

    $ export KORAIL_ID='12345678'
    $ export KORAIL_PW='...'
    $ python -m unittest test.test_korail

예약을 실제로 생성/취소하는 테스트는 사고 방지를 위해 별도 opt-in 이 필요하다.

    $ export KORAIL_ALLOW_BOOKING=1

요청/응답 덤프는 암호화된 비밀번호와 세션 쿠키까지 로그에 남기므로 기본은 꺼둔다.

    $ export KORAIL_DEBUG=1
"""
import logging
import os
import unittest
from datetime import date, timedelta
from unittest import TestCase

from korail2 import (AdultPassenger, ChildPassenger, Korail, KorailError,
                     NoResultsError, ReserveOption, SeniorPassenger,
                     SoldOutError)

__author__ = 'sng2c'

KORAIL_ID = os.environ.get('KORAIL_ID')
KORAIL_PW = os.environ.get('KORAIL_PW')

HAS_CREDENTIALS = bool(KORAIL_ID and KORAIL_PW)
ALLOW_BOOKING = os.environ.get('KORAIL_ALLOW_BOOKING') == '1'

if os.environ.get('KORAIL_DEBUG') == '1':
    # 주의: 요청 본문과 쿠키가 그대로 찍힌다. 로그를 공유하지 말 것.
    import http.client as http_client

    http_client.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


@unittest.skipUnless(HAS_CREDENTIALS,
                     "KORAIL_ID / KORAIL_PW 환경변수가 없어 통합 테스트를 건너뜁니다.")
class TestKorail(TestCase):

    def thetime(self):
        return date.today() + timedelta(days=30)

    def setUp(self):
        self.korail = Korail(KORAIL_ID, KORAIL_PW, auto_login=False)
        if not self.korail.login():
            # 비밀번호는 절대 메시지에 담지 않는다.
            self.fail("Login failed for KORAIL_ID=%s" % KORAIL_ID)

    def test_login(self):
        self.assertTrue(self.korail.login())
        self.assertTrue(self.korail.logined, "로그인 성공 체크")

    def test_logout(self):
        self.korail.logout()
        self.assertFalse(self.korail.logined, "로그아웃 성공 체크")

    def test_search_train(self):
        trains = self.korail.search_train("서울", "부산",
                                          self.thetime().strftime("%Y%m%d"), "100000")
        self.assertGreaterEqual(len(trains), 0, "tomorrow train search")

        alltrains = self.korail.search_train_allday("서울", "부산",
                                                    self.thetime().strftime("%Y%m%d"), "100000")
        self.assertGreaterEqual(len(alltrains), len(trains), "tomorrow train search")

    def test_tickets(self):
        try:
            tickets = self.korail.tickets()
        except KorailError as e:
            self.skipTest(str(e))
        self.assertIsInstance(tickets, list)

    def test_reservations(self):
        try:
            reserves = self.korail.reservations()
        except KorailError as e:
            self.skipTest(str(e))
        self.assertIsNotNone(reserves, "get reservation list")
        self.assertIsInstance(reserves, list)

    def _reserve_and_cancel(self, trains, passengers=None,
                            option=ReserveOption.GENERAL_FIRST):
        empty_seats = list(filter(lambda x: x.has_seat(), trains))
        if not empty_seats:
            self.skipTest("No Empty Seats.")

        try:
            rsv = self.korail.reserve(empty_seats[0], passengers=passengers,
                                      option=option)
        except SoldOutError:
            self.skipTest("Sold Out")

        self.assertIsNotNone(rsv, "make a reservation")
        try:
            matched = list(filter(lambda x: x.rsv_id == rsv.rsv_id,
                                  self.korail.reservations()))
            self.assertEqual(len(matched), 1, "make a reservation")
        finally:
            self.korail.cancel(rsv)

        matched = list(filter(lambda x: x.rsv_id == rsv.rsv_id,
                              self.korail.reservations()))
        self.assertEqual(len(matched), 0, "cancel the reservation")

    @unittest.skipUnless(ALLOW_BOOKING,
                         "KORAIL_ALLOW_BOOKING=1 이 아니면 실제 예약 테스트를 건너뜁니다.")
    def test_reserve_and_cancel(self):
        try:
            trains = self.korail.search_train("서울", "부산",
                                              self.thetime().strftime("%Y%m%d"), "100000")
        except NoResultsError:
            self.skipTest("No results")
        self._reserve_and_cancel(trains)

    @unittest.skipUnless(ALLOW_BOOKING,
                         "KORAIL_ALLOW_BOOKING=1 이 아니면 실제 예약 테스트를 건너뜁니다.")
    def test_reserve_and_cancel_special_only(self):
        try:
            trains = self.korail.search_train("서울", "부산",
                                              self.thetime().strftime("%Y%m%d"), "100000")
        except NoResultsError:
            self.skipTest("No results")

        specials = list(filter(lambda x: x.has_special_seat(), trains))
        if not specials:
            self.skipTest("No special seats.")
        self._reserve_and_cancel(specials, option=ReserveOption.SPECIAL_ONLY)

    @unittest.skipUnless(ALLOW_BOOKING,
                         "KORAIL_ALLOW_BOOKING=1 이 아니면 실제 예약 테스트를 건너뜁니다.")
    def test_reserve_and_cancel_multi(self):
        passengers = (
            AdultPassenger(1),
            ChildPassenger(1),
            SeniorPassenger(1),
        )
        try:
            trains = self.korail.search_train("서울", "부산",
                                              self.thetime().strftime("%Y%m%d"), "100000",
                                              passengers=passengers)
        except NoResultsError:
            self.skipTest("No results")
        self._reserve_and_cancel(trains, passengers=passengers)

    @unittest.skipUnless(ALLOW_BOOKING,
                         "KORAIL_ALLOW_BOOKING=1 이 아니면 계정의 전체 예약을 취소하지 않습니다.")
    def test_cancel_all(self):
        for rsv in self.korail.reservations():
            self.korail.cancel(rsv)
        self.assertFalse(self.korail.reservations())
