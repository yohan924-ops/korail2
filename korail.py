#!/usr/bin/env python3
"""코레일 자동 예매 매크로.

사용법:
    export KORAIL_ID=회원번호_또는_이메일_또는_010-xxxx-xxxx
    export KORAIL_PW=비밀번호
    python korail.py --dep 서울 --arr 부산 --date 20260601 --time 100000

지정한 조건의 좌석이 열리는 즉시 예약을 시도하고, 성공하면 종료한다.
"""
import argparse
import os
import sys
import time
from datetime import datetime

from korail2 import (
    AdultPassenger,
    ChildPassenger,
    Korail,
    KorailError,
    NeedToLoginError,
    NoResultsError,
    ReserveOption,
    SeniorPassenger,
    SoldOutError,
    TrainType,
)

TRAIN_TYPES = {
    "ALL": TrainType.ALL,
    "KTX": TrainType.KTX,
    "KTX_SANCHEON": TrainType.KTX_SANCHEON,
    "SAEMAEUL": TrainType.SAEMAEUL,
    "ITX_SAEMAEUL": TrainType.ITX_SAEMAEUL,
    "MUGUNGHWA": TrainType.MUGUNGHWA,
    "NURIRO": TrainType.NURIRO,
    "ITX_CHEONGCHUN": TrainType.ITX_CHEONGCHUN,
}

RESERVE_OPTIONS = {
    "GENERAL_FIRST": ReserveOption.GENERAL_FIRST,
    "GENERAL_ONLY": ReserveOption.GENERAL_ONLY,
    "SPECIAL_FIRST": ReserveOption.SPECIAL_FIRST,
    "SPECIAL_ONLY": ReserveOption.SPECIAL_ONLY,
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_args():
    p = argparse.ArgumentParser(description="코레일 자동 예매 매크로")
    p.add_argument("--id", default=os.environ.get("KORAIL_ID"),
                   help="코레일 ID (기본: KORAIL_ID 환경변수)")
    p.add_argument("--pw", default=os.environ.get("KORAIL_PW"),
                   help="코레일 PW (기본: KORAIL_PW 환경변수)")
    p.add_argument("--dep", required=True, help="출발역 (예: 서울)")
    p.add_argument("--arr", required=True, help="도착역 (예: 부산)")
    p.add_argument("--date", required=True, help="출발일 yyyyMMdd")
    p.add_argument("--time", default="000000", help="출발 시각 hhmmss (기본: 000000)")
    p.add_argument("--time-end", default=None,
                   help="검색 종료 시각 hhmmss (지정 시 이 시각 이후 출발 열차는 제외)")
    p.add_argument("--train-type", default="ALL", choices=list(TRAIN_TYPES.keys()))
    p.add_argument("--train-no", action="append", default=[],
                   help="특정 열차번호만 노림 (여러 번 지정 가능)")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--seniors", type=int, default=0)
    p.add_argument("--reserve-option", default="GENERAL_FIRST",
                   choices=list(RESERVE_OPTIONS.keys()))
    p.add_argument("--try-waiting", action="store_true",
                   help="좌석이 없으면 일반실 예약대기를 시도")
    p.add_argument("--interval", type=float, default=3.0,
                   help="조회 간격(초). 너무 짧으면 차단될 수 있음")
    p.add_argument("--max-attempts", type=int, default=0,
                   help="0이면 무한 반복")
    p.add_argument("--list-only", action="store_true",
                   help="예약 시도 없이 검색된 열차 목록만 출력하고 종료")
    return p.parse_args()


def build_passengers(adults, children, seniors):
    psgrs = []
    if adults > 0:
        psgrs.append(AdultPassenger(adults))
    if children > 0:
        psgrs.append(ChildPassenger(children))
    if seniors > 0:
        psgrs.append(SeniorPassenger(seniors))
    return psgrs or [AdultPassenger(1)]


def filter_candidates(trains, args, reserve_option, train_no_filter):
    out = trains
    if args.time_end:
        out = [t for t in out if t.dep_time <= args.time_end]
    if train_no_filter:
        out = [t for t in out if t.train_no in train_no_filter]

    def usable(t):
        if reserve_option == ReserveOption.GENERAL_ONLY:
            ok = t.has_general_seat()
        elif reserve_option == ReserveOption.SPECIAL_ONLY:
            ok = t.has_special_seat()
        else:
            ok = t.has_seat()
        if not ok and args.try_waiting and reserve_option != ReserveOption.SPECIAL_ONLY:
            ok = t.has_general_waiting_list()
        return ok

    return [t for t in out if usable(t)]


def main():
    args = parse_args()
    if not args.id or not args.pw:
        sys.exit("KORAIL_ID/KORAIL_PW 환경변수 또는 --id/--pw 인자가 필요합니다.")

    psgrs = build_passengers(args.adults, args.children, args.seniors)
    train_type = TRAIN_TYPES[args.train_type]
    reserve_option = RESERVE_OPTIONS[args.reserve_option]
    train_no_filter = set(args.train_no) if args.train_no else None

    log(f"로그인 시도: {args.id}")
    k = Korail(args.id, args.pw, auto_login=False)
    if not k.login():
        sys.exit("로그인 실패")
    log(f"로그인 성공: {k.name}")
    log(f"조건: {args.dep}→{args.arr} {args.date} {args.time}"
        f"{'~' + args.time_end if args.time_end else ''} "
        f"승객={args.adults}성인+{args.children}아동+{args.seniors}경로 "
        f"열차={args.train_type} 옵션={args.reserve_option} "
        f"대기={'on' if args.try_waiting else 'off'} 간격={args.interval}s")

    if args.list_only:
        try:
            trains = k.search_train_allday(
                args.dep, args.arr, args.date, args.time,
                train_type=train_type, passengers=psgrs,
                include_no_seats=True,
            )
        except NoResultsError:
            log("검색 결과 없음")
            return
        if args.time_end:
            trains = [t for t in trains if t.dep_time <= args.time_end]
        log(f"검색 결과 {len(trains)}건"
            f"{' (' + args.time + '~' + args.time_end + ' 범위)' if args.time_end else ''}:")
        for t in trains:
            print(f"  {t.train_no:>4}  {t.dep_time[:2]}:{t.dep_time[2:4]}"
                  f"~{t.arr_time[:2]}:{t.arr_time[2:4]}  "
                  f"{t.dep_name}→{t.arr_name}  "
                  f"일반={'O' if t.has_general_seat() else '-'}"
                  f"/특실={'O' if t.has_special_seat() else '-'}"
                  f"/대기={'O' if t.has_general_waiting_list() else '-'}  "
                  f"{t.train_type_name}", flush=True)
        return

    attempt = 0
    while True:
        attempt += 1
        if args.max_attempts and attempt > args.max_attempts:
            log(f"최대 시도 횟수({args.max_attempts}) 도달. 종료.")
            sys.exit(2)

        try:
            trains = k.search_train_allday(
                args.dep, args.arr, args.date, args.time,
                train_type=train_type, passengers=psgrs,
                include_no_seats=args.try_waiting,
            )
        except NeedToLoginError:
            log("세션 만료 → 재로그인")
            k.login()
            continue
        except NoResultsError:
            log(f"#{attempt} 좌석 없음")
            time.sleep(args.interval)
            continue
        except KorailError as e:
            log(f"#{attempt} 검색 오류: {e}")
            time.sleep(args.interval)
            continue
        except Exception as e:
            log(f"#{attempt} 기타 오류: {type(e).__name__}: {e}")
            time.sleep(args.interval)
            continue

        candidates = filter_candidates(trains, args, reserve_option, train_no_filter)
        if not candidates:
            log(f"#{attempt} 조건 일치 열차 없음 (검색 {len(trains)}건)")
            time.sleep(args.interval)
            continue

        log(f"#{attempt} 후보 {len(candidates)}개 → 예약 시도")
        booked = False
        for t in candidates:
            try:
                rsv = k.reserve(t, passengers=psgrs, option=reserve_option,
                                try_waiting=args.try_waiting)
                log(f"✓ 예약 성공: {rsv}")
                booked = True
                break
            except SoldOutError:
                log(f"  매진: {t}")
                continue
            except NeedToLoginError:
                log("  세션 만료 → 재로그인 후 재시도")
                k.login()
                break
            except KorailError as e:
                log(f"  예약 실패: {t} ({e})")
                continue

        if booked:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("중단됨")
        sys.exit(130)
