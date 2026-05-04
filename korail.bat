@echo off
chcp 949 >nul
setlocal enabledelayedexpansion
title 코레일 자동 예매 매크로
cd /d "%~dp0"


REM ============================================================
REM   1단계: 로그인
REM ============================================================
:STEP1
cls
echo.
echo  ============================================
echo             [ 1 / 4 ]   로그인
echo  ============================================
echo.
echo   코레일 계정을 입력하세요.
echo   ^(보안을 위해 자동 저장하지 않습니다. 매 실행마다 입력 필요^)
echo.
set "KORAIL_ID="
set "KORAIL_PW="
set /p KORAIL_ID=     ID  ^(회원번호/이메일/010-XXXX-XXXX^):
set /p KORAIL_PW=     비밀번호:
echo.
echo     [Enter] 이 정보로 로그인
echo     [B]     다시 입력
echo     [Q]     종료
set /p CONFIRM1=     선택:
if /i "!CONFIRM1!"=="q" goto END
if /i "!CONFIRM1!"=="b" goto STEP1

:STEP1_VERIFY
echo.
echo   --- 로그인 확인 중... ---
echo.
python korail.py --id "!KORAIL_ID!" --pw "!KORAIL_PW!" --login-test
if errorlevel 1 goto STEP1_FAIL
goto STEP1_DONE

:STEP1_FAIL
echo.
echo   [X] 로그인 실패. ID/PW를 다시 입력하세요.
echo.
pause
goto STEP1

:STEP1_DONE
echo.
echo   [O] 로그인 성공! 다음 단계로 이동합니다.
echo.
pause


REM ============================================================
REM   2단계: 기차 검색
REM ============================================================
:STEP2
cls
echo.
echo  ============================================
echo             [ 2 / 4 ]   기차 검색
echo  ============================================
echo.
echo   원하는 시간대에 어떤 열차가 운행하는지 확인합니다.
echo.

set /p DEP=     출발역  ^(예: 서울^):
set /p ARR=     도착역  ^(예: 부산^):
set /p DATE_=     출발일  ^(YYYYMMDD^):
set /p TIME_=     시작 시각 ^(HHMMSS, 비우면 000000^):
if "!TIME_!"=="" set TIME_=000000
set /p TIME_END=     종료 시각 ^(HHMMSS, 비우면 종일^):

echo.
:STEP2_TT
echo   열차 종류:
echo     1) KTX (KTX-산천 포함^)
echo     2) ALL (모든 종류^)
echo     3) ITX-새마을
echo     4) 무궁화호
set /p TT_CHOICE=     선택 [1]:
if "!TT_CHOICE!"=="" set TT_CHOICE=1
set "TRAIN_TYPE="
if "!TT_CHOICE!"=="1" set TRAIN_TYPE=KTX
if "!TT_CHOICE!"=="2" set TRAIN_TYPE=ALL
if "!TT_CHOICE!"=="3" set TRAIN_TYPE=ITX_SAEMAEUL
if "!TT_CHOICE!"=="4" set TRAIN_TYPE=MUGUNGHWA
if not defined TRAIN_TYPE (
    echo   [!] 1~4 중에서 선택하세요.
    goto STEP2_TT
)

echo.
echo   --- 검색 중... ---
echo.

set SEARCH_ARGS=--id "!KORAIL_ID!" --pw "!KORAIL_PW!" --dep !DEP! --arr !ARR! --date !DATE_! --time !TIME_! --train-type !TRAIN_TYPE! --list-only
if not "!TIME_END!"=="" set SEARCH_ARGS=!SEARCH_ARGS! --time-end !TIME_END!

python korail.py !SEARCH_ARGS!

echo.
echo  --------------------------------------------
echo     [Y/Enter] 예매 조건 설정으로
echo     [R]       검색 조건 다시 입력
echo     [B]       이전 단계 ^(로그인^)으로
echo     [Q]       종료
echo  --------------------------------------------
set /p NEXT=     선택:
if "!NEXT!"=="" set NEXT=y
if /i "!NEXT!"=="q" goto END
if /i "!NEXT!"=="b" goto STEP1
if /i "!NEXT!"=="r" goto STEP2


REM ============================================================
REM   3단계: 자동 예매 조건 선택
REM ============================================================
:STEP3
cls
echo.
echo  ============================================
echo             [ 3 / 4 ]   예매 조건 선택
echo  ============================================
echo.
echo   검색 결과에서 어떤 차를 어떤 좌석으로 잡을지 정합니다.
echo.

:STEP3_RO
echo   좌석 등급:
echo     1) 일반실 우선 ^(없으면 특실^)
echo     2) 일반실만
echo     3) 특실 우선   ^(없으면 일반실^)
echo     4) 특실만
set /p RO_CHOICE=     선택 [1]:
if "!RO_CHOICE!"=="" set RO_CHOICE=1
set "RESERVE_OPTION="
if "!RO_CHOICE!"=="1" set RESERVE_OPTION=GENERAL_FIRST
if "!RO_CHOICE!"=="2" set RESERVE_OPTION=GENERAL_ONLY
if "!RO_CHOICE!"=="3" set RESERVE_OPTION=SPECIAL_FIRST
if "!RO_CHOICE!"=="4" set RESERVE_OPTION=SPECIAL_ONLY
if not defined RESERVE_OPTION (
    echo   [!] 1~4 중에서 선택하세요.
    goto STEP3_RO
)

echo.
echo   인원:
set /p ADULTS=     어른   [1]:
if "!ADULTS!"=="" set ADULTS=1
set /p CHILDREN=     어린이 [0]:
if "!CHILDREN!"=="" set CHILDREN=0
set /p SENIORS=     경로   [0]:
if "!SENIORS!"=="" set SENIORS=0

echo.
set /p YN_WAIT=     매진 시 예약대기까지 시도? ^(y/n^) [y]:
if "!YN_WAIT!"=="" set YN_WAIT=y
set TRY_WAITING=
if /i "!YN_WAIT!"=="y" set TRY_WAITING=--try-waiting

echo.
set /p INTERVAL=     조회 간격(초^) [3]:
if "!INTERVAL!"=="" set INTERVAL=3

echo.
echo  --------------------------------------------
echo     [Y/Enter] 다음 ^(예매 시작 화면^)으로
echo     [B]       이전 단계 ^(기차 검색^)으로
echo     [R]       이 단계 다시 입력
echo     [Q]       종료
echo  --------------------------------------------
set /p NEXT3=     선택:
if "!NEXT3!"=="" set NEXT3=y
if /i "!NEXT3!"=="q" goto END
if /i "!NEXT3!"=="b" goto STEP2
if /i "!NEXT3!"=="r" goto STEP3


REM ============================================================
REM   4단계: 예매 시작
REM ============================================================
:STEP4
cls
echo.
echo  ============================================
echo             [ 4 / 4 ]   예매 시작
echo  ============================================
echo.
echo   아래 조건으로 자동 예매를 시작합니다.
echo  --------------------------------------------
echo     계정      : !KORAIL_ID!
echo     구간      : !DEP!  -^>  !ARR!
echo     출발일    : !DATE_!
echo     시간대    : !TIME_!  ~  !TIME_END!
echo     열차      : !TRAIN_TYPE!
echo     좌석      : !RESERVE_OPTION!
echo     인원      : 어른 !ADULTS! / 어린이 !CHILDREN! / 경로 !SENIORS!
if defined TRY_WAITING echo     예약대기  : ON
echo     조회간격  : !INTERVAL!초
echo  --------------------------------------------
echo.
echo   * 좌석이 풀리는 즉시 예약하고 종료합니다.
echo   * 중지하려면 Ctrl+C를 누르세요.
echo   * 예약 성공 시 코레일톡/홈페이지에서 시간 내 결제하세요.
echo.
echo     [Y/Enter] 시작
echo     [B]       이전 단계 ^(예매 조건^)으로
echo     [Q]       종료
set /p START=     선택:
if "!START!"=="" set START=y
if /i "!START!"=="q" goto END
if /i "!START!"=="b" goto STEP3

cls
set ARGS=--id "!KORAIL_ID!" --pw "!KORAIL_PW!" --dep !DEP! --arr !ARR! --date !DATE_! --time !TIME_! --train-type !TRAIN_TYPE! --reserve-option !RESERVE_OPTION! --adults !ADULTS! --children !CHILDREN! --seniors !SENIORS! --interval !INTERVAL!
if not "!TIME_END!"=="" set ARGS=!ARGS! --time-end !TIME_END!
if defined TRY_WAITING set ARGS=!ARGS! !TRY_WAITING!

python korail.py !ARGS!


:END
echo.
echo  ============================================
echo            매크로 종료
echo  ============================================
pause
endlocal
