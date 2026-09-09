# -*- coding: utf-8 -*-
"""가짜 HTTP 세션으로 공개 API 흐름 전체를 구동하는 테스트.

네트워크도 계정도 필요 없다. 실제 코레일 응답 형태를 흉내내어
요청 조립(승객 수, 좌석 등급, 예약/예약대기 구분)과 응답 파싱을 검증한다.
"""
import json
from unittest import TestCase

from korail2 import (AdultPassenger, ChildPassenger, Korail, NoResultsError,
                     ReserveOption, SeniorPassenger, SoldOutError, TrainType)
from korail2.korail2 import (KORAIL_CANCEL, KORAIL_MYRESERVATIONLIST,
                             KORAIL_SEARCH_SCHEDULE, KORAIL_TICKETRESERVATION)

SUCC = {'strResult': 'SUCC', 'h_msg_cd': 'S000', 'h_msg_txt': ''}
NO_RESULTS = {'strResult': 'FAIL', 'h_msg_cd': 'P100', 'h_msg_txt': '조회 결과가 없습니다'}


def train_info(train_no, dep_tm, arr_tm, gen='11', spe='11', wait='-2'):
    """열차 조회 응답 1건."""
    return {
        'h_trn_clsf_cd': '00', 'h_trn_clsf_nm': 'KTX', 'h_trn_gp_cd': '100',
        'h_trn_no': train_no, 'h_expct_dlay_hr': '0',
        'h_dpt_rs_stn_nm': '서울', 'h_dpt_rs_stn_cd': '0001',
        'h_dpt_dt': '20260923', 'h_dpt_tm': dep_tm,
        'h_arv_rs_stn_nm': '부산', 'h_arv_rs_stn_cd': '0020',
        'h_arv_dt': '20260923', 'h_arv_tm': arr_tm,
        'h_run_dt': '20260923',
        'h_rsv_psb_flg': 'Y', 'h_rsv_psb_nm': '예약가능',
        'h_spe_rsv_cd': spe, 'h_gen_rsv_cd': gen, 'h_wait_rsv_flg': wait,
    }


def reservation_info(train_no, dep_tm, arr_tm):
    """예약 목록 응답 1건."""
    data = train_info(train_no, dep_tm, arr_tm)
    # 실제 예약 응답에는 좌석 여유 표시가 들어있지 않다.
    data.pop('h_rsv_psb_nm')
    data.update({
        'h_pnr_no': 'PNR%s' % train_no, 'h_tot_seat_cnt': '002',
        'h_ntisu_lmt_dt': '20260918', 'h_ntisu_lmt_tm': '140500',
        'h_rsv_amt': '00085000', 'txtJrnySqno': '001',
        'txtJrnyCnt': '01', 'hidRsvChgNo': '00000',
    })
    return data


def schedule_payload(*infos):
    payload = dict(SUCC)
    payload['trn_infos'] = {'trn_info': list(infos)}
    return payload


class FakeResponse(object):
    def __init__(self, payload):
        self.text = json.dumps(payload)


class FakeSession(object):
    """URL 로 라우팅하는 가짜 requests.Session."""

    def __init__(self, schedule_payloads=None):
        self.headers = {}
        self.requests = []
        # 조회 응답을 순서대로 소비한다. 다 떨어지면 마지막 것을 반복.
        self.schedule_payloads = list(schedule_payloads or [])

    def _payload_for(self, url):
        if url == KORAIL_SEARCH_SCHEDULE:
            if not self.schedule_payloads:
                return NO_RESULTS
            if len(self.schedule_payloads) == 1:
                return self.schedule_payloads[0]
            return self.schedule_payloads.pop(0)
        if url == KORAIL_TICKETRESERVATION:
            payload = dict(SUCC)
            payload['h_pnr_no'] = 'PNR101'
            return payload
        if url == KORAIL_MYRESERVATIONLIST:
            payload = dict(SUCC)
            payload['jrny_infos'] = {'jrny_info': [
                {'train_infos': {'train_info': [
                    reservation_info('101', '100000', '124200')]}}]}
            return payload
        if url == KORAIL_CANCEL:
            return dict(SUCC)
        raise AssertionError("unexpected url: %s" % url)

    def _route(self, url, params=None, data=None):
        self.requests.append((url, dict(params or data or {})))
        return FakeResponse(self._payload_for(url))

    def get(self, url, params=None, data=None):
        return self._route(url, params, data)

    def post(self, url, params=None, data=None):
        return self._route(url, params, data)


class FlowTestCase(TestCase):
    """로그인된 Korail 인스턴스를 가짜 세션에 물려둔다."""

    schedule_payloads = None

    def setUp(self):
        self.korail = Korail('dummy', 'dummy', auto_login=False)
        self.session = FakeSession(self.schedule_payloads)
        self.korail._session = self.session
        self.korail._key = 'FAKEKEY'
        self.korail.logined = True

    def last_request(self, url):
        for req_url, params in reversed(self.session.requests):
            if req_url == url:
                return params
        raise AssertionError("no request to %s" % url)

    def requests_to(self, url):
        return [p for u, p in self.session.requests if u == url]


class TestSearchTrain(FlowTestCase):
    schedule_payloads = [schedule_payload(
        train_info('101', '100000', '124200'),
        train_info('103', '110000', '134200', gen='13', spe='13'),
        train_info('105', '120000', '144200', gen='13', spe='13', wait='9'),
    )]

    def test_returns_only_trains_with_seats(self):
        trains = self.korail.search_train("서울", "부산", "20260923", "100000")
        self.assertEqual(len(trains), 1)
        self.assertEqual(trains[0].train_no, '101')

    def test_include_no_seats(self):
        trains = self.korail.search_train("서울", "부산", "20260923", "100000",
                                          include_no_seats=True)
        self.assertEqual(len(trains), 3)

    def test_include_waiting_list(self):
        trains = self.korail.search_train("서울", "부산", "20260923", "100000",
                                          include_waiting_list=True)
        self.assertEqual([t.train_no for t in trains], ['101', '105'])

    def test_passenger_counts_in_request(self):
        self.korail.search_train("서울", "부산", "20260923", "100000",
                                 train_type=TrainType.KTX,
                                 passengers=[AdultPassenger(2), ChildPassenger(1),
                                             SeniorPassenger(1)])
        params = self.last_request(KORAIL_SEARCH_SCHEDULE)
        self.assertEqual(params['txtPsgFlg_1'], 2)   # 어른
        self.assertEqual(params['txtPsgFlg_2'], 1)   # 어린이
        self.assertEqual(params['txtPsgFlg_8'], 0)   # 유아
        self.assertEqual(params['txtPsgFlg_3'], 1)   # 경로
        self.assertEqual(params['selGoTrain'], TrainType.KTX)
        self.assertEqual(params['txtGoStart'], '서울')
        self.assertEqual(params['txtGoEnd'], '부산')

    def test_defaults_to_one_adult(self):
        self.korail.search_train("서울", "부산", "20260923", "100000")
        params = self.last_request(KORAIL_SEARCH_SCHEDULE)
        self.assertEqual(params['txtPsgFlg_1'], 1)


class TestSearchTrainNoResults(FlowTestCase):
    schedule_payloads = []

    def test_raises_no_results(self):
        with self.assertRaises(NoResultsError):
            self.korail.search_train("서울", "부산", "20260923", "100000")


class TestSearchTrainAllday(FlowTestCase):
    # 1페이지 -> 2페이지 -> 결과 없음
    schedule_payloads = [
        schedule_payload(train_info('101', '100000', '124200'),
                         train_info('103', '103000', '130000', gen='13', spe='13')),
        schedule_payload(train_info('105', '140000', '164200')),
        NO_RESULTS,
    ]

    def test_pages_until_no_results(self):
        trains = self.korail.search_train_allday("서울", "부산", "20260923", "100000")
        self.assertEqual([t.train_no for t in trains], ['101', '105'])

    def test_advances_departure_time_by_one_minute(self):
        self.korail.search_train_allday("서울", "부산", "20260923", "100000")
        hours = [p['txtGoHour'] for p in self.requests_to(KORAIL_SEARCH_SCHEDULE)]
        # 1페이지 마지막 열차가 10:30 출발 -> 다음 조회는 10:31 부터
        self.assertEqual(hours[0], '100000')
        self.assertEqual(hours[1], '103100')

    def test_include_waiting_list_is_passed_through(self):
        # 매진이지만 예약대기 가능한 열차가 살아남아야 한다.
        self.session.schedule_payloads = [
            schedule_payload(train_info('201', '100000', '124200',
                                        gen='13', spe='13', wait='9')),
            NO_RESULTS,
        ]
        trains = self.korail.search_train_allday("서울", "부산", "20260923", "100000",
                                                 include_waiting_list=True)
        self.assertEqual([t.train_no for t in trains], ['201'])

    def test_without_waiting_list_sold_out_is_dropped(self):
        self.session.schedule_payloads = [
            schedule_payload(train_info('201', '100000', '124200',
                                        gen='13', spe='13', wait='9')),
            NO_RESULTS,
        ]
        with self.assertRaises(NoResultsError):
            self.korail.search_train_allday("서울", "부산", "20260923", "100000")


class TestSearchTrainAlldayStopsAtMidnight(FlowTestCase):
    schedule_payloads = [
        schedule_payload(train_info('101', '235900', '020000')),
        schedule_payload(train_info('999', '000100', '030000')),
    ]

    def test_does_not_search_into_next_day(self):
        trains = self.korail.search_train_allday("서울", "부산", "20260923", "230000")
        self.assertEqual([t.train_no for t in trains], ['101'])
        self.assertEqual(len(self.requests_to(KORAIL_SEARCH_SCHEDULE)), 1)


class TestReserve(FlowTestCase):
    schedule_payloads = [schedule_payload(
        train_info('101', '100000', '124200'),
        train_info('103', '110000', '134200', gen='13', spe='13'),
        train_info('105', '120000', '144200', gen='13', spe='13', wait='9'),
    )]

    def _trains(self):
        return self.korail.search_train("서울", "부산", "20260923", "100000",
                                        include_no_seats=True)

    def test_reserve_returns_matching_reservation(self):
        rsv = self.korail.reserve(self._trains()[0])
        self.assertEqual(rsv.rsv_id, 'PNR101')
        self.assertEqual(rsv.seat_no_count, 2)
        self.assertEqual(rsv.price, 85000)

    def test_general_first_picks_general_seat(self):
        self.korail.reserve(self._trains()[0])
        params = self.last_request(KORAIL_TICKETRESERVATION)
        self.assertEqual(params['txtPsrmClCd1'], '1')
        self.assertEqual(params['txtJobId'], '1101')

    def test_special_only_picks_special_seat(self):
        self.korail.reserve(self._trains()[0], option=ReserveOption.SPECIAL_ONLY)
        self.assertEqual(self.last_request(KORAIL_TICKETRESERVATION)['txtPsrmClCd1'], '2')

    def test_general_only_on_special_only_train_raises(self):
        train = self._trains()[0]
        train.general_seat = '13'  # 일반실 매진, 특실만 남음
        with self.assertRaises(SoldOutError):
            self.korail.reserve(train, option=ReserveOption.GENERAL_ONLY)

    def test_sold_out_train_raises(self):
        with self.assertRaises(SoldOutError):
            self.korail.reserve(self._trains()[1])

    def test_try_waiting_enrolls_in_waiting_list(self):
        waiting_train = self._trains()[2]
        self.korail.reserve(waiting_train, try_waiting=True)
        params = self.last_request(KORAIL_TICKETRESERVATION)
        self.assertEqual(params['txtJobId'], '1102')  # 1102 = 예약대기
        self.assertEqual(params['txtPsrmClCd1'], '1')

    def test_try_waiting_still_raises_without_waiting_list(self):
        with self.assertRaises(SoldOutError):
            self.korail.reserve(self._trains()[1], try_waiting=True)

    def test_passenger_dicts_are_indexed(self):
        self.korail.reserve(self._trains()[0],
                            passengers=[AdultPassenger(2), ChildPassenger(1)])
        params = self.last_request(KORAIL_TICKETRESERVATION)
        self.assertEqual(params['txtTotPsgCnt'], 3)
        self.assertEqual(params['txtPsgTpCd1'], '1')
        self.assertEqual(params['txtCompaCnt1'], 2)
        self.assertEqual(params['txtPsgTpCd2'], '3')
        self.assertEqual(params['txtCompaCnt2'], 1)

    def test_journey_fields_come_from_train(self):
        train = self._trains()[0]
        self.korail.reserve(train)
        params = self.last_request(KORAIL_TICKETRESERVATION)
        self.assertEqual(params['txtTrnNo1'], train.train_no)
        self.assertEqual(params['txtDptRsStnCd1'], train.dep_code)
        self.assertEqual(params['txtArvRsStnCd1'], train.arr_code)
        self.assertEqual(params['txtRunDt1'], train.run_date)


class TestReservationsAndCancel(FlowTestCase):
    def test_reservations_are_parsed(self):
        reserves = self.korail.reservations()
        self.assertEqual(len(reserves), 1)
        rsv = reserves[0]
        self.assertEqual(rsv.rsv_id, 'PNR101')
        # 응답에 빠져 있는 출/도착 날짜는 운행일로 채운다.
        self.assertEqual(rsv.dep_date, '20260923')
        self.assertIn('85000원(2석)', repr(rsv))
        self.assertIn('구입기한', repr(rsv))

    def test_cancel_sends_reservation_identifiers(self):
        rsv = self.korail.reservations()[0]
        self.assertTrue(self.korail.cancel(rsv))
        params = self.last_request(KORAIL_CANCEL)
        self.assertEqual(params['txtPnrNo'], rsv.rsv_id)
        self.assertEqual(params['txtJrnySqno'], rsv.journey_no)
        self.assertEqual(params['txtJrnyCnt'], rsv.journey_cnt)
        self.assertEqual(params['hidRsvChgNo'], rsv.rsv_chg_no)

    def test_cancel_rejects_non_reservation(self):
        with self.assertRaises(AssertionError):
            self.korail.cancel("PNR101")
