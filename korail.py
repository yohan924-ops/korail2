# -*- coding: utf-8 -*-
"""좌석이 날 때까지 검색을 반복하다가 예약하는 예제 스크립트.

자격증명은 절대 소스에 적지 말고 환경변수로 넘깁니다.

    $ export KORAIL_ID='12345678'       # 회원번호 / 이메일 / 전화번호
    $ export KORAIL_PW='...'
    $ python korail.py

검색 조건도 환경변수로 덮어쓸 수 있습니다.

    $ KORAIL_DEP=서울 KORAIL_ARR=구포 KORAIL_DEP_DATE=20260101 python korail.py
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from korail2 import (AdultPassenger, Korail, KorailError, NoResultsError,
                     TrainType)

KORAIL_ID = os.environ.get('KORAIL_ID')
KORAIL_PW = os.environ.get('KORAIL_PW')

# Pushover 를 쓰려면 환경변수로 토큰을 넣어주세요. 없으면 알림은 건너뜁니다.
PUSHOVER_APP_TOKEN = os.environ.get('PUSHOVER_APP_TOKEN')
PUSHOVER_USER_TOKEN = os.environ.get('PUSHOVER_USER_TOKEN')

# 코레일 API 는 한국시간 기준이므로 기본값도 KST 로 계산합니다.
_KST_NOW = datetime.now(timezone(timedelta(hours=9)))

DEP = os.environ.get('KORAIL_DEP', '서울')
ARV = os.environ.get('KORAIL_ARR', '구포')
DEP_DATE = os.environ.get('KORAIL_DEP_DATE', _KST_NOW.strftime('%Y%m%d'))
DEP_TIME = os.environ.get('KORAIL_DEP_TIME', _KST_NOW.strftime('%H%M%S'))
PSGRS = [AdultPassenger(1)]
TRAIN_TYPE = TrainType.KTX


def sendnoti(msg):
    """알림 훅. Pushover 등을 여기에 연결하세요."""
    if not (PUSHOVER_APP_TOKEN and PUSHOVER_USER_TOKEN):
        return
    # 실제 전송은 구현되어 있지 않습니다.


def main():
    if not (KORAIL_ID and KORAIL_PW):
        print("환경변수 KORAIL_ID, KORAIL_PW 를 설정해주세요.", file=sys.stderr)
        return 2

    k = Korail(KORAIL_ID, KORAIL_PW, auto_login=False)
    if not k.login():
        print("login fail", file=sys.stderr)
        return 1

    while True:
        trains = None
        while trains is None:
            try:
                sys.stdout.write("Finding Seat %s -> %s              \r" % (DEP, ARV))
                sys.stdout.flush()
                trains = k.search_train_allday(DEP, ARV, DEP_DATE, DEP_TIME,
                                               passengers=PSGRS, train_type=TRAIN_TYPE)
                print(trains)
                print("Found!!")
            except NoResultsError:
                sys.stdout.write("No Seats                               \r")
                sys.stdout.flush()
                time.sleep(2)
            except KorailError as e:
                print(e, file=sys.stderr)
                time.sleep(2)

        k.login()
        try:
            seat = k.reserve(trains[0], passengers=PSGRS)
        except KorailError as e:
            print(e, file=sys.stderr)
            sendnoti(str(e))
            return 1

        print(seat)
        sendnoti(repr(seat))
        return 0


if __name__ == '__main__':
    sys.exit(main())
