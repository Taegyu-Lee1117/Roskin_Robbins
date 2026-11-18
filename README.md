# Roskin Robbins

**ROS 2와 Doosan M0609를 이용한 아이스크림 제조 자동화 시스템**

웹 키오스크의 주문을 FastAPI와 PostgreSQL로 관리하고, ROS 2 Action으로 컵 공급부터 아이스크림 스쿠핑, 배출, 완성 컵 제공과 홈 복귀까지 연결한 프로젝트입니다. 주문 진행 상황과 로봇 상태는 브리지를 거쳐 웹 화면에 반영합니다.

## 시연 영상

[![Roskin Robbins 시연 영상](https://img.youtube.com/vi/kTLdnDv2gPA/hqdefault.jpg)](https://www.youtube.com/watch?v=kTLdnDv2gPA)

## 담당 역할

스쿠핑 동작과 힘 감지 로직을 담당했습니다. 기존 제조 공정에 표면 접촉 감지, 단계별 추가 진입, CURL 스쿠핑과 후퇴·상승을 통합하고, 동작 종료 시점의 현재 TCP에서 컵 이동 경로로 이어지도록 구성했습니다.

- Fx/Fz baseline 대비 변화량으로 접촉을 판정하고, 1mm 하강과 연속 2회 감지 조건을 적용했습니다.
- 접촉 후 최대 7mm 추가 진입에 단계별 힘 검사와 Z 하한을 적용했습니다.
- 현재 TCP 위치에서 수직화한 뒤 스쿱 회전과 X축 후퇴를 결합하는 CURL 동작을 연결했습니다.
- 제한된 벽 접근 경로에 방향성 반력 감시를 적용하고, 접근 종료 후 후퇴와 수직 상승을 연결했습니다.
- 진입 델타 15N과 축별 절대 힘 40N의 의미를 유지하고, TCP·힘 조회 반환값을 검사하도록 구성했습니다.

담당 기능의 구현은 스쿠핑 모듈, 공통 로봇 제어 래퍼와 모션 설정에서 확인할 수 있습니다. [스쿠핑 모듈](src/icecream_pj/icecream_pj/scoop.py), [공통 모션](src/icecream_pj/icecream_pj/motion_common.py), [모션 설정](src/icecream_pj/icecream_pj/motion_config.py)

## 시스템 구성

<img src="src/system_architecture.png" alt="키오스크, FastAPI, PostgreSQL, 주문 브리지, ROS 2 제조 서버와 M0609의 연결 구조" width="1000">

| 구성 요소 | 역할 |
| --- | --- |
| 키오스크·관리자 UI | 맛 선택과 주문 접수, 제조 진행 표시, 관리자 수동 명령 |
| FastAPI · PostgreSQL | 주문·오류·로봇 상태 저장, REST API와 WebSocket 피드백 제공 |
| 주문 브리지 | HTTP 주문을 ROS 2 Action으로 전달하고 진행 상황과 결과를 API에 반영 |
| 제조 Action Server | 컵·스쿱·서빙 모션의 순차 실행과 단계별 오류 전달 |
| Doosan ROS 2 Driver | M0609의 관절·직선 이동과 디지털 I/O, 도구 힘 조회 |

주문 브리지는 대기 주문을 선점한 뒤 `/make_icecream` Goal을 전송합니다. 제조 서버는 단계별 Feedback을 발행하고, 브리지는 이를 주문 진행률과 로봇 상태로 변환해 API와 UI에 전달합니다.

<details>
<summary>주문 접수부터 완료까지의 전체 플로우차트</summary>

<img src="docs/flow_chart.png" alt="키오스크 주문 접수, 제조 요청, 컵 제공과 오류 처리의 전체 흐름" width="700">

</details>

## 제조 공정

<img src="docs/manufacturing_sequence.png" alt="초기화부터 컵 파지, 힘 기반 스쿠핑, 배출, 서빙과 홈 복귀까지의 제조 타임라인" width="1200">

그림은 정상 제조 흐름을 12개 동작 묶음으로 표현합니다. 제품 제공 완료 시 주문 완료를 알리고, 홈 복귀가 성공하면 로봇을 다음 주문을 받을 수 있는 상태로 전환합니다.

## 스쿠핑 제어 설계

<img src="docs/force_guided_scoop.png" alt="접촉 탐색, 추가 진입, 수직화와 CURL, 벽 접근, 후퇴와 상승의 상태 전이 및 힘 판정 기준" width="1200">

### 기준값 대비 변화량으로 표면 접촉 판정

진입 자세에서 측정되는 힘의 편향을 기준값에 반영하기 위해 Fx/Fz를 0.06초 간격으로 5회 측정하고 각 성분을 평균합니다. 현재 TCP에서 Z축을 1mm씩 내리며 다음 변화량을 계산합니다.

```text
Δ = sqrt((Fx - baseline_Fx)² + (Fz - baseline_Fz)²)
```

Δ가 1.3N 이상인 상태를 2회 연속 확인하면 접촉으로 판정합니다. 기준 미달 시 연속 횟수를 초기화하며, Z 하한에서 접촉 후보가 한 번 나오면 같은 높이에서 한 번 더 측정합니다.

### 현재 TCP를 기준으로 퍼담기와 이송 연결

| 구간 | 제어 방식 |
| --- | --- |
| 추가 진입 | 접촉 높이에서 2mm씩 최대 7mm 하강하며 Z=115.29mm 하한 적용 |
| 수직화 | 현재 X/Y/Z를 유지한 채 스쿱 자세 전환 |
| CURL | Y/Z를 유지하며 자세 회전과 X축 최대 20mm 후퇴 결합 |
| 벽 접근 | CURL 종료점에서 +X로 2mm씩 최대 6mm 접근하며 Fx 반력 증가 감시 |
| 후퇴·상승 | 현재 TCP에서 -X로 5mm 후퇴 후 최대 25mm씩 Z=320mm까지 상승 |
| 컵 이동 | 상승을 마친 현재 TCP에서 레인별 경유점을 구성해 컵 투입 목표로 이동 |

벽 접근의 반력 증가량은 CURL 종료 자세에서 읽은 Fx를 기준으로 `baseline_Fx - Fx`로 계산합니다. 반력 증가가 5N에 도달하거나 최대 이동거리를 채우면 접근을 마치고 후퇴합니다.

### 힘 기준과 중단 조건

| 기준 | 계산에 사용하는 값 | 적용 구간 |
| --- | --- | --- |
| 1.3N 연속 2회 | Fx/Fz baseline 대비 벡터 변화량 Δ | 표면 접촉 판정 |
| 15N | 동일한 진입 baseline 대비 Δ | 탐색·하한 재확인·추가 진입 중단 |
| 40N | Fx/Fy/Fz 중 각 축의 절댓값 | 각 힘 측정에서 한계 도달 여부 확인 |
| 5N | 벽 접근 시작 Fx 대비 방향성 반력 증가량 | 제한된 벽 접근 종료 |

힘은 각 이동 단계가 끝난 뒤 확인합니다. 힘 한계 도달이나 잘못된 센서 반환값은 예외로 전달해 후속 제조 동작을 중단합니다. 접촉을 확인하지 못한 경우에는 현재 X/Y와 자세를 유지한 채 Z=250mm까지 상승하고 스쿠핑 실패를 전달합니다.

자세, 속도와 힘 임계값은 설정 파일에 모아 관리합니다. [모션 설정](src/icecream_pj/icecream_pj/motion_config.py), [스쿠핑 상세 기술문서](src/DOCUMENT.md#93-힘-기반-진입과-스쿠핑)

## 공정 통합에서의 설계

| 다룬 상황 | 구현 방식 |
| --- | --- |
| 주문 조회 후 같은 주문을 다시 수령하는 경우 | `PENDING` 상태를 조건으로 `PROCESSING`으로 변경하는 주문 선점 API 사용 |
| 제조 진행 상황을 웹에서 확인해야 하는 경우 | Action Feedback의 단계명을 브리지에서 진행률·메시지로 변환하고 WebSocket으로 전달 |
| 제품 제공 후 홈 복귀가 실패하는 경우 | 결과의 `order_completed`와 `robot_ready`를 각각 관리해 주문 완료와 로봇 준비 상태 구분 |
| 제조 명령과 관리자 수동 명령이 겹치는 경우 | 제조 서버의 `busy_lock`으로 실행 진입을 관리하고 제조 중 일반 수동 명령 거부 |
| 동기 로봇 API를 호출하며 Action을 처리하는 경우 | Action 처리 노드와 DSR API 노드를 분리해 제조 서버 구성 |

관련 구현은 주문 선점 API, 주문 브리지와 제조 서버에서 확인할 수 있습니다. [FastAPI](backend/app/main.py), [주문 브리지](src/icecream_pj/icecream_pj/integrated_order_bridge.py), [제조 서버](src/icecream_pj/icecream_pj/make_icecream_server.py)

## 개발 환경과 기술 스택

| 분야 | 사용 기술 |
| --- | --- |
| 로봇·장비 | Doosan M0609, 컵·스쿱 그리퍼, 디지털 I/O 센서 |
| 운영체제·언어 | Ubuntu 24.04.4 LTS, Python 3.12 |
| 로봇 소프트웨어 | ROS 2 Jazzy, Doosan Robotics API, Action, Service |
| 백엔드·데이터 | FastAPI, PostgreSQL 16, psycopg |
| 웹 UI | HTML, CSS, JavaScript, WebSocket |

## 코드 구조

```text
Roskin_Robbins/
├── backend/                         # FastAPI, PostgreSQL 스키마·마이그레이션
├── docs/                            # 공정도와 스쿠핑 상세도 PNG·SVG
├── src/
│   ├── icecream_pj/
│   │   ├── icecream_pj/
│   │   │   ├── scoop.py              # 스쿠핑과 컵 투입·스쿱 반환
│   │   │   ├── motion_common.py      # 공통 이동·I/O·TCP·힘 조회
│   │   │   ├── motion_config.py      # 좌표·속도·힘 임계값
│   │   │   ├── make_icecream_server.py
│   │   │   ├── integrated_order_bridge.py
│   │   │   ├── cup.py
│   │   │   └── serve.py
│   │   └── launch/                  # 로봇·제조 서버·브리지 통합 실행
│   ├── icecream_interfaces/         # MakeIcecream Action, AdminCommand Service
│   ├── frontend/                    # 키오스크·관리자 화면
│   ├── backend/                     # 제출용 백엔드
│   ├── README.md                    # 설치·빌드·실행 안내
│   └── DOCUMENT.md                  # 시스템 상세 기술문서
├── history/                         # 이전 프로젝트 버전
└── run_system.sh                    # 통합 실행 스크립트
```

## 실행 및 상세 문서

DB 초기화, 의존성 설치와 ROS 2 패키지 빌드 순서는 실행 문서에 정리되어 있습니다. [설치·빌드·실행 안내](src/README.md), [백엔드 설정](backend/README.md)

<details>
<summary>기본 실행 명령과 웹 주소</summary>

아래 `<workspace>`는 이 저장소를 클론하고 빌드한 ROS 2 워크스페이스, `<doosan_ws>`는 Doosan ROS 2 패키지를 빌드한 워크스페이스입니다.

PostgreSQL과 FastAPI를 실행합니다.

```bash
sudo systemctl start postgresql

cd <workspace>/backend
source .venv/bin/activate
export DATABASE_URL=postgresql://icecream:icecream@127.0.0.1:5432/icecream_db

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

별도 터미널에서 로봇과 ROS 2 노드를 실행합니다.

```bash
cd <workspace>
export ROS_DOMAIN_ID=30
source /opt/ros/jazzy/setup.bash
source <doosan_ws>/install/setup.bash
source install/setup.bash

ros2 launch icecream_pj icecream_system.launch.py
```

| 화면 | 주소 |
| --- | --- |
| 키오스크 | http://127.0.0.1:8000/kiosk |
| 관리자 | http://127.0.0.1:8000/admin |
| 데이터베이스 조회 | http://127.0.0.1:8000/database |
| API 문서 | http://127.0.0.1:8000/docs |

실제 로봇 실행 전 TCP/Tool 설정, 작업 좌표, 비상정지 장치와 주변 작업 상태를 확인해야 합니다.

</details>

- [시스템 상세 기술문서](src/DOCUMENT.md)
- [이전 버전 기록](history/README.md)

## 참고 자료

- [Doosan Robotics ROS 2](https://github.com/DoosanRobotics/doosan-robot2)
- [Doosan Robotics Programming Manual](https://manual.doosanrobotics.com/ko/programming-manual/3.3.0/publish/)
- [스쿠핑 실험 코드와 CURL 기준 모션](https://github.com/tnduaehowl12/scooping-motion-drl)

## 라이선스

ROS 2 패키지는 Apache License 2.0을 사용합니다.
