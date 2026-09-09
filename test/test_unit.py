# -*- coding: utf-8 -*-
"""네트워크와 코레일 계정 없이 도는 순수 로직 테스트."""
from unittest import TestCase
from unittest import mock

from korail2 import (AdultPassenger, ChildPassenger, Korail, KorailError,
                     NeedToLoginError, NoResultsError, Passenger,
                     ReserveOption, SeniorPassenger, ToddlerPassenger,
                     TrainType)
from korail2.korail2 import Reservation, Schedule, Train


def _train_data(**overrides):
    data = {
        'h_trn_clsf_cd': '00',
        'h_trn_clsf_nm': 'KTX',
        'h_trn_gp_cd': '100',
        'h_trn_no': '101',
        'h_expct_dlay_hr': '0',
        'h_dpt_rs_stn_nm': '서울',
        'h_dpt_rs_stn_cd': '0001',
        'h_dpt_dt': '20260815',
        'h_dpt_tm': '110000',
        'h_arv_rs_stn_nm': '부산',
        'h_arv_rs_stn_cd': '0020',
        'h_arv_dt': '20260815',
        'h_arv_tm': '134200',
        'h_run_dt': '20260815',
        'h_rsv_psb_flg': 'Y',
        'h_rsv_psb_nm': '예약가능',
        'h_spe_rsv_cd': '11',
        'h_gen_rsv_cd': '11',
        'h_wait_rsv_flg': '-2',
    }
    data.update(overrides)
    return data


class TestPassenger(TestCase):
    def test_abstract(self):
        with self.assertRaises(NotImplementedError):
            Passenger()

    def test_reduce_rejects_non_passenger(self):
        with self.assertRaises(TypeError):
            Passenger.reduce([AdultPassenger(), "aaaa"])

    def test_reduce_drops_non_positive(self):
        reduced = Passenger.reduce([
            AdultPassenger(), AdultPassenger(), AdultPassenger(count=-1),
            ChildPassenger(count=0), SeniorPassenger(count=-1),
        ])
        self.assertEqual(len(reduced), 1)
        self.assertIsInstance(reduced[0], AdultPassenger)
        self.assertEqual(reduced[0].count, 1)

    def test_reduce_groups_same_type(self):
        reduced = Passenger.reduce([
            AdultPassenger(), AdultPassenger(), ChildPassenger(),
            SeniorPassenger(), SeniorPassenger(),
        ])
        counts = {type(p): p.count for p in reduced}
        self.assertEqual(counts[AdultPassenger], 2)
        self.assertEqual(counts[ChildPassenger], 1)
        self.assertEqual(counts[SeniorPassenger], 2)

    def test_toddler_is_distinct_from_child(self):
        # 둘 다 typecode '3' 이지만 할인 타입이 달라 합쳐지면 안 된다.
        self.assertEqual(ToddlerPassenger().typecode, ChildPassenger().typecode)
        self.assertNotEqual(ToddlerPassenger().discount_type,
                            ChildPassenger().discount_type)
        reduced = Passenger.reduce([ChildPassenger(), ToddlerPassenger()])
        self.assertEqual(len(reduced), 2)

    def test_get_dict(self):
        d = AdultPassenger(2).get_dict(1)
        self.assertEqual(d['txtPsgTpCd1'], '1')
        self.assertEqual(d['txtCompaCnt1'], 2)
        self.assertEqual(d['txtDiscKndCd1'], '000')


class TestTrain(TestCase):
    def test_seat_flags(self):
        train = Train(_train_data())
        self.assertTrue(train.has_special_seat())
        self.assertTrue(train.has_general_seat())
        self.assertTrue(train.has_seat())

    def test_sold_out(self):
        train = Train(_train_data(h_spe_rsv_cd='13', h_gen_rsv_cd='13'))
        self.assertFalse(train.has_seat())
        self.assertFalse(train.has_waiting_list())

    def test_waiting_list(self):
        train = Train(_train_data(h_spe_rsv_cd='13', h_gen_rsv_cd='13',
                                  h_wait_rsv_flg='9'))
        self.assertFalse(train.has_seat())
        self.assertTrue(train.has_waiting_list())

    def test_missing_wait_flag(self):
        data = _train_data()
        del data['h_wait_rsv_flg']
        self.assertFalse(Train(data).has_waiting_list())

    def test_repr(self):
        text = repr(Train(_train_data()))
        self.assertIn('KTX', text)
        self.assertIn('서울~부산', text)
        self.assertIn('11:00~13:42', text)


class TestReservation(TestCase):
    def test_fields_and_repr(self):
        data = _train_data(h_pnr_no='123456', h_tot_seat_cnt='002',
                           h_ntisu_lmt_dt='20260810', h_ntisu_lmt_tm='140500',
                           h_rsv_amt='00042500')
        rsv = Reservation(data)
        self.assertEqual(rsv.rsv_id, '123456')
        self.assertEqual(rsv.seat_no_count, 2)
        self.assertEqual(rsv.price, 42500)
        # 응답에 빠져 있는 dep/arr 날짜는 운행일로 채운다.
        self.assertEqual(rsv.dep_date, '20260815')
        self.assertEqual(rsv.journey_no, '001')
        self.assertIn('42500원(2석)', repr(rsv))


class TestTrainType(TestCase):
    def test_tongguen_alias(self):
        self.assertEqual(TrainType.TONGGEUN, '103')
        self.assertEqual(TrainType.TONGGUEN, TrainType.TONGGEUN)

    def test_not_instantiable(self):
        with self.assertRaises(NotImplementedError):
            TrainType()
        with self.assertRaises(NotImplementedError):
            ReserveOption()


class TestErrorCodes(TestCase):
    def test_code_membership(self):
        self.assertIn('P100', NoResultsError)
        self.assertIn('P058', NeedToLoginError)
        self.assertNotIn('P058', NoResultsError)

    def test_str(self):
        self.assertEqual(str(KorailError('boom', 'X1')), 'boom (X1)')


class TestResultCheck(TestCase):
    def setUp(self):
        self.korail = Korail('id', 'pw', auto_login=False)

    def test_success(self):
        self.assertTrue(self.korail._result_check(
            {'strResult': 'SUCC', 'h_msg_cd': 'P000', 'h_msg_txt': 'OK'}))

    def test_generic_failure(self):
        with self.assertRaises(KorailError):
            self.korail._result_check(
                {'strResult': 'FAIL', 'h_msg_cd': 'P000', 'h_msg_txt': 'UNKNOWN'})

    def test_no_results(self):
        with self.assertRaises(NoResultsError):
            self.korail._result_check(
                {'strResult': 'FAIL', 'h_msg_cd': 'P100', 'h_msg_txt': 'UNKNOWN'})

    def test_need_to_login(self):
        with self.assertRaises(NeedToLoginError):
            self.korail._result_check(
                {'strResult': 'FAIL', 'h_msg_cd': 'P058', 'h_msg_txt': 'UNKNOWN'})


class TestSessionIsolation(TestCase):
    def test_sessions_are_per_instance(self):
        a = Korail('a', 'pw', auto_login=False)
        b = Korail('b', 'pw', auto_login=False)
        self.assertIsNot(a._session, b._session)

    def test_user_agent_set(self):
        a = Korail('a', 'pw', auto_login=False)
        self.assertIn('User-Agent', a._session.headers)


class TestEncPassword(TestCase):
    """암호화 키 조회 실패가 조용히 넘어가지 않는지 확인."""

    def _korail_with_response(self, payload):
        korail = Korail('id', 'pw', auto_login=False)
        response = mock.Mock()
        response.text = payload
        korail._session = mock.Mock()
        korail._session.post.return_value = response
        return korail

    def test_raises_when_key_unavailable(self):
        korail = self._korail_with_response('{"strResult": "FAIL"}')
        with self.assertRaises(KorailError):
            korail.login()

    def test_encrypts_when_key_available(self):
        payload = ('{"strResult": "SUCC", "app.login.cphd": '
                   '{"idx": "7", "key": "0123456789abcdef"}}')
        korail = self._korail_with_response(payload)
        enc = korail._Korail__enc_password('secret')
        self.assertIsInstance(enc, str)
        self.assertTrue(enc)
        self.assertEqual(korail._idx, '7')


class TestLoginIdFormat(TestCase):
    """아이디 형식에 따른 txtInputFlg 분류와 전화번호 정규화."""

    def _flg_and_id(self, korail_id):
        """login() 이 서버로 보낼 txtInputFlg 와 txtMemberNo 를 얻는다."""
        korail = Korail(korail_id, 'pw', auto_login=False)
        sent = {}

        class FakeResponse(object):
            text = '{"strResult": "FAIL", "h_msg_cd": "X", "h_msg_txt": "nope"}'

        def post(url, data=None, **kwargs):
            sent.update(data or {})
            return FakeResponse()

        korail._session = mock.Mock()
        korail._session.post.side_effect = post
        with mock.patch.object(Korail, '_Korail__enc_password',
                               return_value='enc'):
            korail.login()
        return sent['txtInputFlg'], sent['txtMemberNo'], korail

    def test_email(self):
        flg, member_no, _ = self._flg_and_id('carpedm20@gmail.com')
        self.assertEqual(flg, '5')
        self.assertEqual(member_no, 'carpedm20@gmail.com')

    def test_membership_number(self):
        flg, member_no, _ = self._flg_and_id('12345678')
        self.assertEqual(flg, '2')
        self.assertEqual(member_no, '12345678')

    def test_phone_with_hyphens(self):
        flg, member_no, _ = self._flg_and_id('010-1234-5678')
        self.assertEqual(flg, '4')
        self.assertEqual(member_no, '010-1234-5678')

    def test_phone_without_hyphens_is_not_mistaken_for_membership(self):
        # 하이픈 없이 넣어도 전화번호로 인식되어야 한다.
        flg, member_no, _ = self._flg_and_id('01012345678')
        self.assertEqual(flg, '4')
        self.assertEqual(member_no, '010-1234-5678')

    def test_old_style_phone_without_hyphens(self):
        flg, member_no, _ = self._flg_and_id('0111234567')
        self.assertEqual(flg, '4')
        self.assertEqual(member_no, '011-123-4567')

    def test_failure_reason_is_kept(self):
        _, _, korail = self._flg_and_id('12345678')
        self.assertFalse(korail.logined)
        self.assertEqual(korail.last_error_code, 'X')
        self.assertEqual(korail.last_error_message, 'nope')
