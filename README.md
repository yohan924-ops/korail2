
Legal disclaimer
---

**Usage of korail for attacking targets without prior mutual consent is illegal**. It's the end user's responsibility to obey all applicable local, state and federal laws. Developers assume no liability and are not responsible for any misuse or damage caused by this program. Only use for educational purposes.


<br/>

Korail2
=======

![test](https://github.com/yohan924-ops/korail2/actions/workflows/test.yml/badge.svg)

Korail (www.letskorail.com) wrapper for Python.

This project was inspired from [korail](https://github.com/devxoul/korail) of [devxoul](https://github.com/devxoul).


Documentation
-------------

The documentation is available at [here](http://carpedm20.github.io/korail2/)


Requirements
------------

Python 3.8+ (`requests`, `PyCryptodome`).

Installing
----------

To install korail2, simply:

    $ pip install korail2

Or, you can use:

    $ easy_install korail2

Or, you can also install manually:

    $ git clone git://github.com/carpedm20/korail2.git
    $ cd korail2
    $ python setup.py install

Credentials
-----------

**Never hardcode your Korail ID/password in source files.** Read them from
the environment (or a secret manager) instead:

```python
import os
from korail2 import Korail

korail = Korail(os.environ['KORAIL_ID'], os.environ['KORAIL_PW'])
```

The example script `korail.py` and the integration tests both take
`KORAIL_ID` / `KORAIL_PW` from the environment for this reason.
Also note that enabling HTTP debug logging dumps the encrypted password and
session cookies into your logs, so keep it off unless you need it.

Using
-----

### 1. Login ###

First, you need to create a Korail object.

```python
>>> from korail2 import *
>>> korail = Korail("12345678", YOUR_PASSWORD) # with membership number
>>> korail = Korail("carpedm20@gmail.com", YOUR_PASSWORD) # with email
>>> korail = Korail("010-9964-xxxx", YOUR_PASSWORD) # with phone number
```

If you do not want login automatically, 

```python
>>> korail = Korail("12345678", YOUR_PASSWORD, auto_login=False)
>>> korail.login()
True
```

When you want change ID using existing object,

```python
>>> korail.login(ANOTHER_ID, ANOTHER_PASSWORD)
True
```

### 2. Search train ###

You can search train schedules `search_train` and `search_train_allday` methods.

- `search_train` returns 10 results max. Faster than `search_train_allday`.
- `search_train_allday` returns all results after the time.
- `search_train_allday` uses `search_train` repeatedly.

`search_train` and `search_train_allday` methods take these arguments:

- dep : A departure station in Korean  ex) '서울'
- arr : A arrival station in Korean  ex) '부산'
- date : (optional) A departure date in `yyyyMMdd` format
- time : (optional) A departure time in `hhmmss` format
- train_type: (optional) A type of train. You can use constants of TrainType class here.
    default value is TrainType.ALL.
    코레일이 같은 그룹으로 묶는 종별끼리는 코드값이 겹칩니다.
    - 100: TrainType.KTX - KTX
    - 100: TrainType.KTX_SANCHEON - KTX-산천
    - 101: TrainType.SAEMAEUL - 새마을호
    - 101: TrainType.ITX_SAEMAEUL - ITX-새마을
    - 102: TrainType.MUGUNGHWA - 무궁화호
    - 102: TrainType.NURIRO - 누리로
    - 103: TrainType.TONGGEUN - 통근열차
    - 104: TrainType.ITX_CHEONGCHUN - ITX-청춘
    - 105: TrainType.AIRPORT - 공항직통
    - 109: TrainType.ALL - 전체
- (optional) passengers=None : List of Passenger Objects. None means 1 AdultPassenger.
- (optional) include_no_seats=False : When True, a result includes trains which has no seats.
- (optional) include_waiting_list=False : When True, a result also includes sold-out trains
  which still accept a waiting-list reservation (예약 대기).

Below is a sample usage of `search_train`:

```python
>>> dep = '서울'
>>> arr = '동대구'
>>> date = '20140815'
>>> time = '144000'
>>> trains = korail.search_train(dep, arr, date, time)
[[KTX] 8월 3일, 서울~부산(11:00~13:42) 특실,일반실 예약가능,
 [ITX-새마을] 8월 3일, 서울~부산(11:04~16:00) 일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:00~14:43) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:30~15:13) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:40~15:45) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:55~15:26) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(13:00~15:37) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(13:10~15:58) 특실,일반실 예약가능]
```

When you want to see sold-out trains.

```python
>>> trains = korail.search_train(dep, arr, date, time, include_no_seats=True)
[[KTX] 8월 3일, 서울~부산(11:00~13:42) 특실,일반실 예약가능,
 [ITX-새마을] 8월 3일, 서울~부산(11:04~16:00) 일반실 예약가능,
 [무궁화호] 8월 3일, 서울~부산(11:08~16:54) 입석 역발매중,
 [ITX-새마을] 8월 3일, 서울~부산(11:50~16:50) 입석 역발매중,
 [KTX] 8월 3일, 서울~부산(12:00~14:43) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:30~15:13) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:40~15:45) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(12:55~15:26) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(13:00~15:37) 특실,일반실 예약가능,
 [KTX] 8월 3일, 서울~부산(13:10~15:58) 특실,일반실 예약가능]
```

#### 2-1. About `passengers` argument

`passengers` is a list(or tuple) of Passeger Objects.
By this, you can search for multiple passengers.
There are 4 types of Passengers now, AdultPassenger, ChildPassenger,
ToddlerPassenger and SeniorPassenger.

```python
# for 1 adult, 1 child
>>> psgrs = [AdultPassenger(), ChildPassenger()]

# for 2 adults, 1 child
>>> psgrs = [AdultPassenger(2), ChildPassenger(1)]
# ditto. They are being added each other by same group.
>>> psgrs = [AdultPassenger(), AdultPassenger(), ChildPassenger()]

# for 2 adults, 1 child, 1 senior
>>> psgrs = [AdultPassenger(2), ChildPassenger(), SeniorPassenger()]

# for 1 adult, 1 toddler (유아)
>>> psgrs = [AdultPassenger(), ToddlerPassenger()]

# for 1 adult, It supports negative count or zero count. 
# But it uses passengers which the sum is greater than zero.
>>> psgrs = [AdultPassenger(2), AdultPassenger(-1)]
>>> psgrs = [AdultPassenger(), SeniorPassenger(0)]

# Nothing
>>> psgrs = [AdultPassenger(0), SeniorPassenger(0)]

# then search or reserve train
>>> trains = korail.search_train(dep, arr, date, time, passengers=psgrs)
...
>>> korail.reserve(trains[0], psgrs)
...
```

### 3. Make a reservation ####

You can get your tickets with `tickets` method.

```python
>>> trains = korail.search_train(dep, arr, date, time)
>>> seat = korail.reserve(trains[0])
>>> seat
[KTX] 8월 23일, 서울~동대구(15:30~17:19) 42500원(1석), 구입기한 8월 18일 14:05
```

Multiple.

```python
>>> trains = korail.search_train(dep, arr, date, time)
>>> seat = korail.reserve(trains[0], passengers=psgrs)
>>> seat
[KTX] 8월 23일, 서울~동대구(15:30~17:19) 42500원(3석), 구입기한 8월 18일 14:05
```

When tickets are not enough much for passengers, it raises SoldOutError.
    
If you want to select priority of seat grade, general or special,
There are 4 options in ReserveOption class.

- GENERAL_FIRST : Economic than Comfortable.
- GENERAL_ONLY  : Reserve only general seats. You are poorman ;-)
- SPECIAL_FIRST : Comfortable than Economic.
- SPECIAL_ONLY  : Richman.

```python
>>> korail.reserve(trains[0], psgrs, ReserveOption.GENERAL_ONLY)
```

If the train is sold out but still accepts a waiting-list reservation (예약 대기),
pass `try_waiting=True` to enroll in the waiting list instead of raising `SoldOutError`.

```python
>>> trains = korail.search_train(dep, arr, date, time, include_waiting_list=True)
>>> korail.reserve(trains[0], psgrs, try_waiting=True)
```

### 4. Show reservations ####

You can get your tickes with `tickets` method.

```python
>>> reservations = korail.reservations()
>>> reservations
[[KTX] 8월 23일, 서울~동대구(14:55~16:45) 42500원(1석), 구입기한 8월 18일 14:03,
 [무궁화호] 8월 23일, 서울~동대구(15:03~18:48) 21100원(1석), 구입기한 8월 18일 14:03,
 [KTX] 8월 23일, 서울~동대구(15:30~17:19) 42500원(1석), 구입기한 8월 18일 14:05]
```

### 5. Cancel reservation ###

You can also cancel your reservation using Reservation Object from reservations() call.

```python
>>> korail.cancel(reservations[0])
```

### 6. Get tickets already paid ###

You can see your ticket list with `tickets` method.
You can get the list of paid tickes with `tickets` method.

```python
>>> korail = Korail("12345678", YOUR_PASSWORD, want_feedback=True)
>>> tickets = korail.tickets()
정상발매처리,정상발권처리  # You can see these feedbacks when `want_feedback` is True.
>>> print tickets
[[KTX] 8월 10일, 동대구~울산(09:26~09:54) => 5호 4A, 13900원]
```

Todo
----

1. Implement payment API


License
-------

Source codes are distributed under BSD license.


Author
------

Taehoon Kim / [@carpedm20](http://carpedm20.github.io/about/)

Hanson Kim / [@sng2c](https://github.com/sng2c)
