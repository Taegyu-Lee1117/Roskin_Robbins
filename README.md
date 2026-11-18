# Roskin Robbins

ROS 2와 두산 협동로봇을 활용한 아이스크림 제조 자동화 시스템

## 프로젝트 개요

- **목표**: 웹 주문부터 아이스크림 제조와 완성품 제공까지 이어지는 협동로봇 기반 무인 자동화 시스템 구현
- **주요 기능**: 키오스크 주문, 제조 공정 제어, 실시간 상태 표시, 관리자 모니터링 및 수동 제어
- **사용 장비**: Doosan M0609, 컵 그리퍼, 스쿱 그리퍼, 디지털 입출력 센서
- **개발 환경**: Ubuntu 24.04.4 LTS, ROS 2 Jazzy, Python 3.12, PostgreSQL 16
- **주요 기술 스택**: ROS 2, Doosan Robotics API, FastAPI, PostgreSQL, HTML/CSS/JavaScript

## 시연 영상

<div align="center">

[![Roskin Robbins 시연 영상](https://img.youtube.com/vi/kTLdnDv2gPA/hqdefault.jpg)](https://www.youtube.com/watch?v=kTLdnDv2gPA)


</div>

## 담당 역할

스쿠핑 공정과 힘 감지 로직을 담당했습니다. 재료 표면을 탐색한 뒤 추가 진입, 수직화, CURL 스쿠핑과 후퇴·상승을 실행하고, 현재 TCP 위치에서 기존 컵 이동 경로로 이어지도록 구성했습니다.

- **표면 접촉 감지** — Fx/Fz를 5회 측정한 평균을 baseline으로 잡고, Z축을 1mm씩 내리며 baseline 대비 벡터 변화량이 1.3N 이상인 상태를 2회 연속 확인합니다.
- **추가 진입과 힘 제한** — 접촉 후 2mm씩 최대 7mm 추가 진입하며 Z 하한과 진입 델타 15N을 적용합니다. 각 힘 측정에서 Fx/Fy/Fz 축별 절대 힘 40N 제한을 확인합니다.
- **CURL 스쿠핑** — 현재 TCP에서 스쿱을 수직화한 뒤, Y/Z를 유지하며 스쿱 회전과 X축 후퇴를 결합해 재료를 퍼담습니다.
- **벽 접근과 공정 연결** — 최대 6mm의 벽 방향 접근에서 반력 증가를 감시하고, 접근을 마친 뒤 후퇴·상승해 컵 투입 경로로 연결합니다. 힘은 각 이동 단계가 끝난 뒤 확인합니다.

관련 구현은 스쿠핑 모듈, 공통 모션과 모션 설정에서 확인할 수 있습니다. [scoop.py](src/icecream_pj/icecream_pj/scoop.py), [motion_common.py](src/icecream_pj/icecream_pj/motion_common.py), [motion_config.py](src/icecream_pj/icecream_pj/motion_config.py)

## 다이어그램

<div align="center">

### 시스템 아키텍처

<img src="src/system_architecture.png" alt="시스템 아키텍처" width="700">

### 공정 플로우차트

<img src="docs/flow_chart.png" alt="공정 플로우차트" width="700">

</div>

## 상세 설명

### 문제 정의

- 일반적인 협동로봇 예제는 개별 모션 실행에 집중되어 있어 주문 접수, 제조, 상태 관리까지 연결된 서비스형 자동화 사례가 부족합니다.
- 키오스크, 백엔드, 데이터베이스, ROS 2 노드가 분리되어 있으면 주문과 로봇 상태를 일관되게 관리하기 어렵습니다.
- 컵과 스쿱을 다루는 실제 제조 공정에서는 파지 확인, 힘 제어, 일시정지, 오류 처리 등 실기 환경을 고려한 제어가 필요합니다.

### 해결 방안

- 웹 키오스크와 FastAPI를 이용해 사용자 주문을 접수하고 PostgreSQL에 공정 상태를 기록합니다.
- 주문 브리지가 백엔드의 대기 주문을 ROS 2 Action Goal로 변환해 제조 서버에 전달합니다.
- 제조 서버는 컵 공급, 스쿱 파지, 아이스크림 스쿠핑, 컵 투입, 스쿱 반환, 완성품 제공 단계를 순차 실행합니다.
- ROS 2 Action Feedback을 통해 진행 상황을 백엔드와 UI에 반영합니다.
- 관리자 화면과 Service를 이용해 일시정지, 재개, 정지, 홈 이동 및 개별 공정 명령을 처리합니다.

### 주요 기능

- **키오스크 주문**: 맛 선택, 주문 접수, 제조 진행 상태와 결과 표시
- **관리자 제어**: 로봇 상태 확인, 공정 시작/정지, 수동 명령 전송
- **제조 자동화**: 컵 공급부터 완성품 제공까지 단계별 모션 실행
- **ROS 2 연동**: Action 기반 제조 요청과 Feedback, Service 기반 관리자 명령
- **데이터 관리**: 주문 이력, 오류, 로봇 상태, 관리자 명령을 PostgreSQL에 저장
- **안전 제어**: Pause/Resume/Stop, 디지털 입력 기반 파지 확인, 힘 제어 활용
- **모듈화**: 컵, 스쿱, 서빙, 공통 모션을 독립 모듈로 분리해 유지보수성 확보
- **확장성**: 새로운 맛, 공정 단계, 관리자 명령, UI 기능을 추가할 수 있는 구조

## 시스템 구성

| 구성 요소 | 역할 |
| --- | --- |
| 키오스크/관리자 UI | 주문 접수, 공정 상태 표시, 관리자 제어 |
| FastAPI | REST API와 웹 페이지 제공, 상태 전이 및 요청 검증 |
| PostgreSQL | 주문, 오류, 로봇 상태, 관리자 명령 저장 |
| `order_bridge` | HTTP 주문과 ROS 2 Action/Service 변환 |
| `make_icecream_server` | 제조 공정 오케스트레이션 및 Action Server |
| Doosan ROS 2 Driver | M0609 모션, 디지털 I/O, 힘 제어 |

## 공정 흐름

1. 사용자가 키오스크에서 맛을 선택하고 주문합니다.
2. FastAPI가 주문을 PostgreSQL에 저장합니다.
3. `order_bridge`가 가장 오래된 대기 주문을 선점합니다.
4. `/make_icecream` Action Goal을 제조 서버에 전송합니다.
5. 제조 서버가 컵 공급, 스쿱 파지, 스쿠핑, 컵 투입, 스쿱 반환, 컵 제공을 실행합니다.
6. 단계별 Feedback과 성공/실패 결과가 백엔드에 반영됩니다.
7. 키오스크와 관리자 화면이 최신 주문 및 로봇 상태를 표시합니다.

### 로봇 제조 공정

<img src="docs/manufacturing_sequence.png" alt="초기화부터 컵 파지, 힘 기반 스쿠핑, 배출, 서빙과 홈 복귀까지의 제조 공정" width="1200">

그림은 주문 1건의 정상 제조 흐름을 12개 동작으로 묶어 표현한 것입니다.

| 단계 | 구간 | 동작 |
| --- | --- | --- |
| 1~3 | 준비 | 로봇 초기화와 홈 이동, 컵 파지·뒤집기, 작업대에 컵 배치 |
| 4~5 | 스쿱 접근 | 스쿱을 파지하고 안전 경유점을 거쳐 선택 레인의 재료 위로 접근 |
| 6 | 힘 기반 스쿠핑 | 접촉 감지, 추가 진입, 수직화·CURL, 제한된 벽 접근과 후퇴·상승 |
| 7~9 | 컵 투입 | 현재 TCP에서 컵 위로 이동하고 J6 회전으로 배출한 뒤 수직 이탈과 자세 복귀 |
| 10~12 | 제공·복귀 | 스쿱 반환, 완성 컵 제공, 홈 복귀와 다음 주문 대기 |

제품 제공 완료 시 주문 완료를 알리고, 홈 복귀가 성공하면 로봇을 다음 주문을 받을 수 있는 상태로 전환합니다.

## ROS 2 인터페이스

| 종류 | 이름 | 역할 |
| --- | --- | --- |
| Action | `/make_icecream` | 아이스크림 제조 요청, 진행 Feedback, 결과 반환 |
| Service | `/dsr01/admin_command` | 관리자 수동 명령 처리 |
| Service | `/dsr01/dsr_controller2/motion/move_pause` | 로봇 일시정지 |
| Service | `/dsr01/dsr_controller2/motion/move_resume` | 로봇 동작 재개 |
| Service | `/dsr01/dsr_controller2/motion/move_stop` | 로봇 정지 |

## 주요 로봇 설정

- Robot ID: `dsr01`
- Robot Model: `m0609`
- Robot Address: `192.168.1.100:12345`
- TCP: `GripperDA_v1_A3`
- 스쿱 그리퍼: DO 1 / DI 1
- 컵 그리퍼: DO 3 / DI 3
- 그리퍼 열기: DO 2
- ROS Domain ID: `30`

> 실제 로봇 실행 전 TCP/Tool 설정, 작업 좌표, 비상정지 장치 및 주변 안전 상태를 반드시 확인해야 합니다.

## 실행 방법

### Terminal 1: PostgreSQL 및 FastAPI

```bash
sudo systemctl start postgresql

cd backend
source .venv/bin/activate
export DATABASE_URL=postgresql://icecream:icecream@127.0.0.1:5432/icecream_db

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Terminal 2: ROS 2 및 실제 로봇

```bash
export ROS_DOMAIN_ID=30
source /opt/ros/jazzy/setup.bash
source <doosan_ws>/install/setup.bash
source install/setup.bash

ros2 launch icecream_pj icecream_system.launch.py
```

### 웹 페이지

- 키오스크: <http://127.0.0.1:8000/kiosk>
- 관리자 화면: <http://127.0.0.1:8000/admin>
- 데이터베이스 조회: <http://127.0.0.1:8000/database>
- API 문서: <http://127.0.0.1:8000/docs>

## 프로젝트 구조

```text
icecream_pj/
├── backend/                    # FastAPI 및 PostgreSQL
├── docs/                       # README 이미지
├── history/                    # 이전 프로젝트 버전
├── src/
│   ├── README.md               # 제출 및 실행 안내
│   ├── DOCUMENT.md             # 시스템 상세 기술문서
│   ├── backend/                # 제출용 백엔드
│   ├── frontend/               # 키오스크 및 관리자 UI
│   ├── icecream_interfaces/    # ROS 2 Action 및 Service
│   └── icecream_pj/            # ROS 2 Python 패키지
├── ui_preview/                 # 웹 UI 미리보기
├── 협동1.mp4                   # 제조 시연 영상
└── run_system.sh               # 통합 실행 스크립트
```

## 상세 문서

- [제출 및 실행 안내](src/README.md)
- [시스템 상세 기술문서](src/DOCUMENT.md)
- [백엔드 안내](backend/README.md)
- [이전 버전 기록](history/README.md)

## 참고 자료

- [Doosan Robotics ROS 2](https://github.com/DoosanRobotics/doosan-robot2)
- [Doosan Robotics Programming Manual](https://manual.doosanrobotics.com/ko/programming-manual/3.3.0/publish/)

## 라이선스

ROS 2 패키지는 Apache License 2.0을 사용합니다.
