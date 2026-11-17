"""스쿱 파지, 힘 기반 스쿠핑, 컵 투입과 반환."""
import math

from . import motion_config as c


class ScoopMotion:
    def __init__(self, robot):
        self.r = robot

    def pick(self):
        self.r.open_gripper()
        self.r.movejx_scoop(c.P_SC_APP, "P_SC_APP", c.VEL_J_SCOOP_SAFE_FAST, c.ACC_J_SCOOP_SAFE_FAST)
        self.r.wait(0.5)
        # 파지점 15mm 위까지는 빠르게, 마지막 15mm만 정밀 속도로 접근
        self.r.movel(c.P_SC_PRE_GRIP, "P_SC_PRE_GRIP", c.VEL_X_SCOOP_PICK_RAPID, c.ACC_X_SCOOP_PICK_RAPID)
        self.r.movel(c.P_SC, "P_SC", c.VEL_X_SCOOP_PICK_FAST, c.ACC_X_SCOOP_PICK_FAST)
        self.r.wait(0.5)
        self.r.grip_with_retry(c.DO_SCOOP_GRIP, c.DI_SCOOP_GRIP, "SCOOP_PICK", "스쿱 파지")
        # 충돌 회피 경유점의 궤적을 보존하도록 작은 반경으로 블렌딩한다.
        self.r.movel(c.P_SC_UP, "P_SC_UP", c.VEL_X_SCOOP_PICK_FAST, c.ACC_X_SCOOP_PICK_FAST,
                     radius=c.SCOOP_TRANSFER_BLEND_RADIUS)

    def move_to_icecream(self, lane_dy):
        self.r.movej(c.J_SC_TRANSFER_SAFE, "J_SC_TRANSFER_SAFE", c.VEL_J_SCOOP_SAFE_FAST, c.ACC_J_SCOOP_SAFE_FAST,
                     radius=c.SCOOP_TRANSFER_BLEND_RADIUS)
        # 높은 안전점에서 진입 접근점까지 블렌딩한다.
        self.r.movejx_scoop(c.with_lane_dy(c.P_ICE_TRANSFER_HIGH, lane_dy), "P_ICE_TRANSFER_HIGH",
                             c.VEL_J_SCOOP_TRANSPORT_FAST, c.ACC_J_SCOOP_TRANSPORT_FAST,
                             radius=c.TRANSFER_BLEND_RADIUS)
        # 힘 기준값을 측정하기 전에 완전히 정지한다.
        self.r.movejx_scoop(c.with_lane_dy(c.P_EN_APP, lane_dy), "P_EN_APP",
                             c.VEL_J_SCOOP_SAFE_FAST, c.ACC_J_SCOOP_SAFE_FAST)
        self.r.wait(1.0)

    def _checked_force(self, step):
        force = self.r.tool_force()
        fx, fy, fz = force[:3]
        self.r.log(f"{step} Fx={fx:.2f} Fy={fy:.2f} Fz={fz:.2f}")
        if max(abs(fx), abs(fy), abs(fz)) >= c.F_EMERGENCY_LIMIT:
            raise RuntimeError(f"{step}: 축별 절대 힘 한계({c.F_EMERGENCY_LIMIT:g}N) 도달")
        return force

    def _entry_baseline(self):
        samples = []
        for index in range(c.ENTRY_BASELINE_SAMPLES):
            if index:
                self.r.wait(c.ENTRY_BASELINE_SAMPLE_GAP)
            samples.append(self._checked_force("ENTRY_BASELINE"))
        fx, fz = (sum(sample[axis] for sample in samples) / len(samples) for axis in (0, 2))
        self.r.log(f"ENTRY_BASELINE 평균 Fx={fx:.3f} Fz={fz:.3f}")
        return fx, fz

    def _entry_delta(self, baseline, step):
        force = self._checked_force(step)
        delta = math.hypot(force[0] - baseline[0], force[2] - baseline[1])
        self.r.log(f"{step} delta_xz={delta:.2f}N")
        if delta >= c.F_ENTRY_HARD_LIMIT_DELTA:
            raise RuntimeError(f"{step}: 진입 델타 하드리밋({c.F_ENTRY_HARD_LIMIT_DELTA:g}N) 도달")
        return delta

    def _probe_surface(self, baseline):
        pose = self.r.current_tcp_pose()
        hits = 0
        while pose[2] > c.ENTRY_MIN_Z:
            pose[2] = max(pose[2] - c.ENTRY_Z_STEP, c.ENTRY_MIN_Z)
            self.r.movel(pose, "ENTRY_PROBE", c.VEL_X_ICE_ENTRY_FAST, c.ACC_X_ICE_ENTRY_FAST)
            self.r.wait(c.ENTRY_Z_SETTLE_WAIT)
            delta = self._entry_delta(baseline, "ENTRY_PROBE")
            hits = hits + 1 if delta >= c.F_ENTRY_DELTA else 0
            if hits >= c.ENTRY_CONSEC_HIT_NEEDED:
                return True

        # 하한에서 접촉 후보가 나오면 같은 높이에서 마지막 샘플을 읽는다.
        if hits == c.ENTRY_CONSEC_HIT_NEEDED - 1:
            self.r.wait(c.ENTRY_Z_SETTLE_WAIT)
            return self._entry_delta(baseline, "ENTRY_PROBE_LIMIT") >= c.F_ENTRY_DELTA
        return False

    def _enter_extra_depth(self, baseline):
        pose = self.r.current_tcp_pose()
        contact_z = pose[2]
        depth_limit = min(c.ENTRY_EXTRA_DEPTH, contact_z - c.ENTRY_MIN_Z)
        depth = 0.0
        while depth < depth_limit:
            depth = min(depth + c.ENTRY_EXTRA_STEP, depth_limit)
            pose[2] = max(contact_z - depth, c.ENTRY_MIN_Z)
            self.r.movel(pose, "ENTRY_EXTRA", c.VEL_X_ICE_ENTRY_FAST, c.ACC_X_ICE_ENTRY_FAST)
            self.r.wait(c.ENTRY_Z_SETTLE_WAIT)
            self._entry_delta(baseline, "ENTRY_EXTRA")

    def _curl(self):
        pose = self.r.current_tcp_pose()
        vertical = pose[:3] + list(c.SCOOP_VERTICAL_ORIENTATION)
        self.r.movel(vertical, "SCOOP_VERTICAL", c.VEL_X_SCOOP_CURL, c.ACC_X_SCOOP_CURL)
        self.r.wait(c.SCOOP_STEP_SETTLE_WAIT)
        self._checked_force("SCOOP_VERTICAL")

        x, y, z = self.r.current_tcp_pose()[:3]
        for index, (dx, rx, ry, rz) in enumerate(c.SCOOP_CURL_SEQUENCE, start=1):
            step = f"SCOOP_CURL_{index}"
            self.r.movel([x + dx, y, z, rx, ry, rz], step, c.VEL_X_SCOOP_CURL, c.ACC_X_SCOOP_CURL)
            self.r.wait(c.SCOOP_STEP_SETTLE_WAIT)
            self._checked_force(step)

    def _approach_wall(self):
        pose = self.r.current_tcp_pose()
        start_x = pose[0]
        baseline_fx = self._checked_force("WALL_BASELINE")[0]
        travel = 0.0
        while travel < c.WALL_APPROACH_MAX:
            travel = min(travel + c.WALL_APPROACH_STEP, c.WALL_APPROACH_MAX)
            pose[0] = start_x + travel
            self.r.movel(pose, "WALL_APPROACH", c.VEL_X_ICE_ENTRY_FAST, c.ACC_X_ICE_ENTRY_FAST)
            self.r.wait(c.SCOOP_STEP_SETTLE_WAIT)
            fx = self._checked_force("WALL_APPROACH")[0]
            # 베이스 +X로 접근할 때 벽이 스쿱에 가하는 반력은 -X 방향이다.
            resistance = baseline_fx - fx
            self.r.log(f"WALL_APPROACH 이동={travel:.1f}mm 반력 증가={resistance:.2f}N")
            if resistance >= c.F_WALL_RESISTANCE_DELTA:
                self.r.log("WALL_APPROACH 반력 한계 도달, 후퇴")
                break

    def _lift_to(self, target_z):
        pose = self.r.current_tcp_pose()
        while pose[2] < target_z:
            pose[2] = min(pose[2] + c.SCOOP_LIFT_STEP, target_z)
            self.r.movel(pose, "SCOOP_LIFT", c.VEL_X_SCOOP_LIFT_FAST, c.ACC_X_SCOOP_LIFT_FAST)
            self._checked_force("SCOOP_LIFT")

    def scoop(self, lane_dy):
        self.r.movel(c.with_lane_dy(c.P_SCOOP_PRE_ENTRY, lane_dy), "P_SCOOP_PRE_ENTRY",
                     c.VEL_X_ICE_APPROACH_FAST, c.ACC_X_ICE_APPROACH_FAST)
        self.r.wait(0.5)

        baseline = self._entry_baseline()
        if not self._probe_surface(baseline):
            self._lift_to(c.P_EN_APP[2])
            raise RuntimeError("Z 하한까지 재료 접촉을 확인하지 못해 스쿠핑을 중단했습니다.")

        self._enter_extra_depth(baseline)
        self._curl()
        self._approach_wall()

        retreat = self.r.current_tcp_pose()
        retreat[0] -= c.SCOOP_RETREAT_X
        self.r.movel(retreat, "SCOOP_RETREAT", c.VEL_X_ICE_ENTRY_FAST, c.ACC_X_ICE_ENTRY_FAST)
        self._checked_force("SCOOP_RETREAT")
        self._lift_to(c.P_ICE_TRANSFER_HIGH[2])
        # 통 위에서 내용물이 안정될 때까지 기다린다.
        self.r.wait(1.0)
        self._checked_force("SCOOP_EXIT")

    def put_in_cup(self, lane_dy):
        """상승을 마친 TCP 위치에서 컵까지 레인별로 이동한다.

        큰 자세 전환은 직선 보간 시 회전 방향이 모호하므로 첫 이동에
        관절 보간을 사용한다. 레인 2는 통 벽과 컵을 피해 Y축을 먼저 맞춘다.
        """
        x, y = self.r.current_tcp_pose()[:2]
        pour = c.P_POUR

        if lane_dy == c.LANE_DY_LIST[0]:
            target = [x, y, *pour[2:]]
            step = "PUT_IN_CUP_Z_UP"
        else:
            target = [x, *pour[1:]]
            step = "PUT_IN_CUP_Z_AND_Y"
        self.r.movejx_scoop(target, step, c.VEL_J_SCOOP_SAFE_FAST, c.ACC_J_SCOOP_SAFE_FAST)
        self.r.movel(pour, "P_POUR", c.VEL_X_FILLED_SCOOP_CARRY, c.ACC_X_FILLED_SCOOP_CARRY)

        self.r.wait(0.5)
        self.r.movej([0, 0, 0, 0, 0, -c.POUR_ANGLE], "아이스크림 배출", c.VEL_J_POUR, c.ACC_J_POUR, relative=True)
        self.r.wait(c.WAIT_DROP)
        self.r.movel([0, 0, 50, 0, 0, 0], "컵 위 Z축 이탈", c.VEL_X_POUR_RETREAT, c.ACC_X_POUR_RETREAT, relative=True)
        self.r.wait(0.5)
        self.r.movej([0, 0, 0, 0, 0, c.POUR_ANGLE], "배출 J6 복귀", c.VEL_J_POUR_RETURN, c.ACC_J_POUR_RETURN, relative=True)
        self.r.wait(0.5)

    def return_scoop(self):
        # 종이컵 적재 위치와의 충돌을 피한 뒤 스쿱 거치대로 이동한다.
        self.r.movel([0, 0, c.SCOOP_RETURN_LIFT_Z, 0, 0, 0], "SCOOP_RETURN_LIFT",
                     c.VEL_X_POUR_RETREAT, c.ACC_X_POUR_RETREAT, relative=True)
        self.r.wait(0.5)
        self.r.movejx_scoop(c.P_SC_APP, "P_SC_APP_RETURN", c.VEL_J_SCOOP_SAFE, c.ACC_J_SCOOP_SAFE)
        self.r.wait(0.5)
        self.r.movel(c.P_SC, "P_SC_RETURN", c.VEL_X_SCOOP_PICK, c.ACC_X_SCOOP_PICK)
        self.r.wait(0.5)
        self.r.open_gripper()
        self.r.movel(c.P_SC_APP, "P_SC_APP_RETREAT", c.VEL_X_SCOOP_PICK, c.ACC_X_SCOOP_PICK)
        self.r.wait(0.5)
