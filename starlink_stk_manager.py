"""
@Author : wwq
@Date ：2025/11/24
@Time ：14:23
@Function :
STK 星链星座仿真管理器
- STK 连接与场景初始化
- Walker-Star 星座创建，（几乎垂直于赤道）
- 收发机配置
- ISL链路建立
- 链路状态导出，卫星位置导出
- 仿真模拟时间为1小时
"""
import os
import time
from datetime import datetime
from typing import Dict, Tuple, Set, List
import datetime
import pandas as pd
from tqdm import tqdm
from comtypes.client import CreateObject, GetActiveObject
from comtypes.gen import STKObjects, STKUtil
import math
import sys

class StarlinkConstellationManager:
    # ==================== 配置常量 ====================
    SCENARIO_NAME: str = "StarLink_sc"
    CONSTELLATION_NAME: str = "StarLink_con"

    # 星座参数
    TOTAL_PLANES: int = 6
    SATS_PER_PLANE: int = 11
    INCLINATION_DEG: float = 90.0  # 或者86.4
    ALTITUDE_KM: float = 780.0  # 或者550
    EARTH_RADIUS_KM: float = 6371.0
    PHASING_FACTOR: int = 1  # 相位因子F

    # 通信参数
    FREQ_GHZ: float = 20.0
    EIRP_DBW: float = 28.6
    G_OVER_T_DBK: float = 21
    DATA_RATE: float = 50.0

    # 时间设置，1小时
    START_TIME_STR = "22 Nov 2025 04:00:00.000"
    STOP_TIME_STR = "22 Nov 2025 05:00:00.000"  # 结束时间设为1小时后
    STEP = 300.0  # 采样步长

    # 路径设置
    DATA_DIR: str = "data"
    LINK_RESULT_PATH: str = os.path.join(DATA_DIR, "link_status.csv")
    POSITION_RESULT_PATH: str = os.path.join(DATA_DIR, "sat_positions.csv")

    def __init__(self):
        """初始化：连接 STK + 创建/获取场景 + 设置时间范围。"""
        self.uiApp = None
        self.stkRoot = None
        self.scenario = None
        self.sat_dict: Dict[str, object] = {}

        os.makedirs(self.DATA_DIR, exist_ok=True)
        self._connect_to_stk()
        self._setup_scenario()

    def _connect_to_stk(self):
        print("尝试连接STK……")
        try:
            self.uiApp = GetActiveObject("STK11.Application")
            print("已连接到正在运行的STK")
        except:
            print("未检测到STK，正在启动新实例……")
            self.uiApp = CreateObject("STK11.Application")
            self.uiApp.Visible = True
            self.uiApp.UserControl = True

        self.stkRoot = self.uiApp.Personality2
        self.stkRoot.UnitPreferences.SetCurrentUnit("DateFormat", "UTCG")

    def _setup_scenario(self):
        try:
            existing_scenario = self.stkRoot.CurrentScenario
            if existing_scenario.InstanceName == self.SCENARIO_NAME:
                print(f"场景{self.SCENARIO_NAME}已经存在,选择该场景并重置状态")
                self.scenario = existing_scenario
        except:
            print("无当前所需场景，创建新场景...")
            self.stkRoot.NewScenario(self.SCENARIO_NAME)
            self.scenario = self.stkRoot.CurrentScenario

        scenario2 = self.scenario.QueryInterface(STKObjects.IAgScenario)
        print("Active scenario =", self.stkRoot.CurrentScenario.InstanceName)
        print("Before:", scenario2.StartTime, scenario2.StopTime)
        # 使用常量类，模拟时间为1小时
        cmd = f'SetTimePeriod * "{self.START_TIME_STR}" "{self.STOP_TIME_STR}"'
        self.stkRoot.ExecuteCommand(cmd)
        self.stkRoot.Rewind()
        print("After:", scenario2.StartTime, scenario2.StopTime)

    """获取已存在的卫星"""

    def get_existing_satellites(self):
        sats = self.scenario.Children.GetElements(STKObjects.eSatellite)
        return {sat.InstanceName: sat for sat in sats}

    """创建星座和卫星"""

    def create_walker_constellation(self):
        print("\n🛰️ 正在创建星座...")
        scenario = self.stkRoot.CurrentScenario
        # 统计星座和卫星数据
        stats = {
            "constellation_new": 0,
            "constellation_exist": 0,
            "sat_new": 0,
            "sat_exist": 0,
        }

        if scenario.Children.Contains(STKObjects.eConstellation, self.CONSTELLATION_NAME):
            stats["constellation_exist"] = 1
            constellation = self.stkRoot.CurrentScenario.Children.Item(self.CONSTELLATION_NAME)
        else:
            stats["constellation_new"] = 1
            constellation = scenario.Children.New(STKObjects.eConstellation, self.CONSTELLATION_NAME)

        # 获取星座接口以便后续添加卫星
        constellation2 = constellation.QueryInterface(STKObjects.IAgConstellation)
        scenario2 = self.scenario.QueryInterface(STKObjects.IAgScenario)
        start_time_str = scenario2.StartTime
        stop_time_str = scenario2.StopTime

        total_sats_count = self.TOTAL_PLANES * self.SATS_PER_PLANE
        with tqdm(total=total_sats_count, desc="创建卫星", file=sys.stdout, ncols=100) as pbar:
            for plane in range(self.TOTAL_PLANES):
                for idx in range(self.SATS_PER_PLANE):
                    sat_name = f"Sat_{plane}_{idx}"
                    sat_exist = self.scenario.Children.Contains(STKObjects.eSatellite, sat_name)
                    if sat_exist:
                        satellite = self.scenario.Children.Item(sat_name)
                        stats["sat_exist"] += 1
                    else:
                        satellite = self.scenario.Children.New(STKObjects.eSatellite, sat_name)
                        stats["sat_new"] += 1

                    # 设置卫星参数
                    sat2 = satellite.QueryInterface(STKObjects.IAgSatellite)
                    sat2.SetPropagatorType(STKObjects.ePropagatorTwoBody)
                    prop = sat2.Propagator.QueryInterface(STKObjects.IAgVePropagatorTwoBody)
                    kepler = prop.InitialState.Representation.ConvertTo(
                        STKUtil.eOrbitStateClassical
                    ).QueryInterface(STKObjects.IAgOrbitStateClassical)
                    kepler.SizeShapeType = STKObjects.eSizeShapeSemimajorAxis
                    shape = kepler.SizeShape.QueryInterface(STKObjects.IAgClassicalSizeShapeSemimajorAxis)
                    semi_major_axis_km = self.ALTITUDE_KM + self.EARTH_RADIUS_KM
                    shape.SemiMajorAxis = semi_major_axis_km
                    shape.Eccentricity = 0.0
                    kepler.Orientation.Inclination = self.INCLINATION_DEG
                    kepler.Orientation.ArgOfPerigee = 0.0
                    kepler.Orientation.AscNodeType = STKObjects.eAscNodeRAAN
                    raan_deg = (180.0 / self.TOTAL_PLANES) * plane
                    asc_node = kepler.Orientation.AscNode.QueryInterface(STKObjects.IAgOrientationAscNodeRAAN)
                    asc_node.Value = raan_deg
                    # 1. 平面内分布: (360 / S) * idx
                    in_plane_angle = (360.0 / self.SATS_PER_PLANE) * idx
                    # 2. 平面间相位偏移: plane * (F * 360 / T)
                    phasing_offset = plane * (self.PHASING_FACTOR * 360.0 / total_sats_count)
                    true_anomaly_deg = (in_plane_angle + phasing_offset) % 360.0
                    kepler.LocationType = STKObjects.eLocationTrueAnomaly
                    loc = kepler.Location.QueryInterface(STKObjects.IAgClassicalLocationTrueAnomaly)
                    loc.Value = true_anomaly_deg
                    prop.InitialState.Representation.Assign(kepler)
                    # 在什么时间段内算轨道
                    prop.StartTime = start_time_str
                    prop.StopTime = stop_time_str
                    prop.Step = 10.0  # 只负责轨道计算的是否精准
                    prop.Propagate()

                    if not sat_exist:
                        constellation2.Objects.AddObject(satellite)

                    pbar.update(1)

        # 输出汇总统计
        if stats["constellation_new"] > 0:
            print(f"✅ 成功新建星座: {self.CONSTELLATION_NAME}")
        else:
            print(f"ℹ️ 已存在星座: {self.CONSTELLATION_NAME}")

        print(f"✅ 成功新建卫星: {stats['sat_new']}")
        print(f"ℹ️ 已存在卫星: {stats['sat_exist']}")

    """确保卫星有发射机和接收机"""

    def ensure_transceiver(self, sat):
        sat_name = sat.InstanceName
        tx_name = f"Tx_{sat_name}"
        rx_name = f"Rx_{sat_name}"

        tx_is_new = False
        rx_is_new = False

        try:
            tx = sat.Children.Item(tx_name)
        except:
            tx = sat.Children.New(STKObjects.eTransmitter, tx_name)
            tx_is_new = True
        self.configure_transmitter(tx)

        try:
            rx = sat.Children.Item(rx_name)
        except:
            rx = sat.Children.New(STKObjects.eReceiver, rx_name)
            rx_is_new = True
        self.configure_receiver(rx)

        return tx, rx, tx_is_new, rx_is_new

    """配置发射机和接收机参数"""

    def configure_transmitter(self, transmitter):
        tx2 = transmitter.QueryInterface(STKObjects.IAgTransmitter)
        tx2.SetModel('Simple Transmitter Model')
        tx_model = tx2.Model.QueryInterface(STKObjects.IAgTransmitterModelSimple)
        tx_model.Frequency = self.FREQ_GHZ
        tx_model.EIRP = self.EIRP_DBW
        tx_model.DataRate = self.DATA_RATE

    def configure_receiver(self, receiver):
        rx2 = receiver.QueryInterface(STKObjects.IAgReceiver)
        rx2.SetModel('Simple Receiver Model')
        rx_model = rx2.Model.QueryInterface(STKObjects.IAgReceiverModelSimple)
        rx_model.GOverT = self.G_OVER_T_DBK
        rx_model.AutoTrackFrequency = True

    """配置所有卫星的收发机，输出汇总统计"""

    def setup_transceivers(self):
        stats = {
            "tx_new": 0,
            "tx_exist": 0,
            "rx_new": 0,
            "rx_exist": 0,
        }
        for sat in tqdm(self.sat_dict.values(), desc="配置收发机", file=sys.stdout, ncols=100):
            tx, rx, tx_is_new, rx_is_new = self.ensure_transceiver(sat)
            if tx_is_new:
                stats["tx_new"] += 1
            else:
                stats["tx_exist"] += 1
            if rx_is_new:
                stats["rx_new"] += 1
            else:
                stats["rx_exist"] += 1

        print(f"✅ 成功新建发射机: {stats['tx_new']}")
        print(f"ℹ️ 已存在发射机: {stats['tx_exist']}")
        print(f"✅ 成功新建接收机: {stats['rx_new']}")
        print(f"ℹ️ 已存在接收机: {stats['rx_exist']}")
        sys.stdout.flush()
        time.sleep(0.2)

    """根据 InstanceName 查找子对象"""

    def get_child_by_name(self, parent, instance_name):
        children = parent.Children
        for i in range(0, children.Count):
            obj1 = children.Item(i)
            if obj1.InstanceName == instance_name:
                return obj1
        return None

    """为每颗卫星与其邻居建立 ISL，并 ComputeAccess"""

    def setup_isl_links(self):
        time.sleep(0.2)
        print("\n🔗 建立星间链路 (ISL)...")
        sys.stdout.flush()

        stats = {
            "links_with_access": 0,
            "links_no_access": 0,
            "links_error": 0,
            "tx_rx_not_found": 0,
        }

        # 收集所有需要处理的链路
        all_links = []
        for name, sat in self.sat_dict.items():
            plane, idx = map(int, name.split('_')[1:])
            neighbors = [
                f"Sat_{plane}_{(idx - 1) % self.SATS_PER_PLANE}",
                f"Sat_{plane}_{(idx + 1) % self.SATS_PER_PLANE}",
                f"Sat_{(plane - 1) % self.TOTAL_PLANES}_{idx}",
                f"Sat_{(plane + 1) % self.TOTAL_PLANES}_{idx}",
            ]
            for nbr in neighbors:
                if nbr in self.sat_dict:
                    all_links.append((name, nbr, sat))

        for name, nbr, sat in tqdm(all_links, desc="建立ISL链路", file=sys.stdout, ncols=100):
            try:
                tx = self.get_child_by_name(sat, f"Tx_{name}")
                rx = self.get_child_by_name(self.sat_dict[nbr], f"Rx_{nbr}")
                if tx is None or rx is None:
                    stats["tx_rx_not_found"] += 1
                    continue

                access = tx.GetAccessToObject(rx)
                access.ComputeAccess()
                # 计算可见性时间段的个数
                intervals = access.ComputedAccessIntervalTimes
                if intervals.Count == 0:
                    stats["links_no_access"] += 1
                else:
                    stats["links_with_access"] += 1
            except Exception as e:
                stats["links_error"] += 1

        # 输出汇总统计
        print(f"✅ 有可见性的ISL链路: {stats['links_with_access']}")
        print(f"ℹ️ 无可见性的ISL链路: {stats['links_no_access']}")
        if stats["tx_rx_not_found"] > 0:
            print(f"⚠️ Tx/Rx未找到: {stats['tx_rx_not_found']}")
        if stats["links_error"] > 0:
            print(f"❌ 建立链路出错: {stats['links_error']}")

    """生成一个星间链路(Inter-Satellite Link,ISL)的唯一配对列表"""

    def _generate_unique_isl_pairs(self) -> List[Tuple[str, str]]:
        pairs: Set[Tuple[str, str]] = set()
        for name in self.sat_dict.keys():
            plane, idx = map(int, name.split('_')[1:])
            neighbors = [
                f"Sat_{plane}_{(idx - 1) % self.SATS_PER_PLANE}",
                f"Sat_{plane}_{(idx + 1) % self.SATS_PER_PLANE}",
                f"Sat_{(plane - 1) % self.TOTAL_PLANES}_{idx}",
                f"Sat_{(plane + 1) % self.TOTAL_PLANES}_{idx}",
            ]
            for nbr in neighbors:
                if nbr in self.sat_dict:
                    a, b = sorted((name, nbr))
                    pairs.add((a, b))
        return list(pairs)

    """导出全时段链路状态时间序列"""

    def export_link_status_time_series(self, step):
        isl_pairs = self._generate_unique_isl_pairs()
        all_data = []

        print(f"\n📊 导出场景时间区间内的链路状态, Step={step}s")
        print(f"    📝 标准依据: QPSK调制, 目标BER=1e-6, 门限Eb/No=10.6dB")

        # 时间格式解析
        fmt_stk = "%d %b %Y %H:%M:%S.%f"
        try:
            global_start_dt = datetime.datetime.strptime(self.START_TIME_STR, fmt_stk)
        except ValueError:
            global_start_dt = datetime.datetime.strptime(self.START_TIME_STR.split('.')[0], "%d %b %Y %H:%M:%S")

        li_elements = ["Time", "Eb/No", "BER", "Range"]

        # 统计变量
        error_count = 0

        for src, dst in tqdm(isl_pairs, desc="计算链路状态", file=sys.stdout, ncols=100):
            sat_src = self.sat_dict.get(src)
            sat_dst = self.sat_dict.get(dst)
            if not sat_src or not sat_dst: continue

            tx = self.get_child_by_name(sat_src, f"Tx_{src}")
            rx = self.get_child_by_name(sat_dst, f"Rx_{dst}")
            if not tx or not rx: continue

            try:
                # 1. 直接从发射机模型获取 DataRate，比从 DataProvider 获取更稳定
                tx2 = tx.QueryInterface(STKObjects.IAgTransmitter)
                tx_model = tx2.Model.QueryInterface(STKObjects.IAgTransmitterModelSimple)
                data_rate_mbps = tx_model.DataRate  # 这是一个固定的属性值

                # 2. 计算 Access
                access = tx.GetAccessToObject(rx)
                access.ComputeAccess()
                intervals = access.ComputedAccessIntervalTimes

                if intervals.Count == 0: continue

                # 3. 获取 Data Provider 接口
                dp_li = access.DataProviders.Item("Link Information").QueryInterface(STKObjects.IAgDataPrvTimeVar)

                for k in range(intervals.Count):
                    interval = intervals.GetInterval(k)

                    # 时间解析，兼容带毫秒和不带毫秒
                    try:
                        int_start_dt = datetime.datetime.strptime(interval[0], fmt_stk)
                        int_stop_dt = datetime.datetime.strptime(interval[1], fmt_stk)
                    except ValueError:
                        fmt_alt = "%d %b %Y %H:%M:%S"
                        int_start_dt = datetime.datetime.strptime(interval[0].split('.')[0], fmt_alt)
                        int_stop_dt = datetime.datetime.strptime(interval[1].split('.')[0], fmt_alt)

                    # 对齐 Grid
                    delta_seconds = (int_start_dt - global_start_dt).total_seconds()
                    if delta_seconds < 0:
                        next_grid_seconds = 0
                    else:
                        next_grid_seconds = math.ceil(delta_seconds / step) * step

                    curr_dt = global_start_dt + datetime.timedelta(seconds=next_grid_seconds)

                    while curr_dt <= int_stop_dt:
                        # 确保只在区间内采样
                        if curr_dt >= int_start_dt:
                            curr_t_str = curr_dt.strftime("%d %b %Y %H:%M:%S.%f")[:-3]

                            try:
                                # === 执行数据获取 ===
                                # 注意：start 和 stop 设为相同，只取这一个点
                                li_res = dp_li.ExecElements(curr_t_str, curr_t_str, step, li_elements)
                                li_ds = li_res.DataSets
                                times = li_ds.GetDataSetByName("Time").GetValues()

                                if times and len(times) > 0:
                                    def get_val(name):
                                        try:
                                            vals = li_ds.GetDataSetByName(name).GetValues()
                                            return vals[0] if vals else None
                                        except:
                                            return None

                                    all_data.append({
                                        "TimeString": times[0],
                                        "Src": src,
                                        "Dst": dst,
                                        "EbNo_dB": get_val("Eb/No"),
                                        "BER": get_val("BER"),
                                        "Range_km": get_val("Range"),
                                        "DataRate_Mbps": data_rate_mbps  # 使用上面获取的固定值
                                    })
                            except Exception as inner_e:
                                pass

                        curr_dt += datetime.timedelta(seconds=step)

            except Exception as e:
                error_count += 1
                if error_count <= 3:  # 只打印前3个错误，避免刷屏
                    print(f"\n❌ 处理链路 {src}->{dst} 时出错: {e}")

        if all_data:
            df = pd.DataFrame(all_data)

            # 常量
            LIGHT_SPEED = 299792.458
            PACKET_SIZE_BITS = 1024 * 8
            REQUIRED_EBNO_DB = 10.6  # QPSK @ 1e-6 BER

            # 1. 数据清洗
            df['EbNo_dB'] = pd.to_numeric(df['EbNo_dB'], errors='coerce').fillna(-999)

            # 2. 计算真实余量Real Link Margin,不是链路剩余带宽
            df['Real_LinkMargin_dB'] = df['EbNo_dB'] - REQUIRED_EBNO_DB

            # 3. 计算带宽 (Bandwidth)
            def calc_bandwidth(row):
                if row['Real_LinkMargin_dB'] >= 0:
                    return row['DataRate_Mbps']
                else:
                    return 0.0

            df['Bandwidth_Mbps'] = df.apply(calc_bandwidth, axis=1)

            # 4. 计算时延Latency，传播时延，表示在链路上的传播所需要的时间
            df['Latency_ms'] = (df['Range_km'] / LIGHT_SPEED) * 1000

            # 5. 计算丢包率PLR，丢包率的计算公式，把误码率BER换成整包丢包率
            df['Packet_Loss_Rate'] = 1 - (1 - df['BER']) ** PACKET_SIZE_BITS
            # df.loc[df['Real_LinkMargin_dB'] < 0, 'Packet_Loss_Rate'] = 1.0
            df['Packet_Loss_Rate'] = df['Packet_Loss_Rate'].fillna(1.0)

            # 6. 格式化这三个数据，保留两位小数
            for col in ['Latency_ms', 'Real_LinkMargin_dB', 'EbNo_dB']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: round(x, 2) if pd.notnull(x) else x)

            # 7. 排序
            try:
                df['dt_temp'] = pd.to_datetime(df['TimeString'], format=fmt_stk, errors='coerce')
                mask = df['dt_temp'].isna()
                if mask.any():
                    df.loc[mask, 'dt_temp'] = pd.to_datetime(df.loc[mask, 'TimeString'], format="%d %b %Y %H:%M:%S",errors='coerce')
                df = df.sort_values(by=['dt_temp', 'Src', 'Dst'])
            except:
                pass

            # 8. 保存
            header = [
                "TimeString", "Src", "Dst","Latency_ms", "Bandwidth_Mbps",
                "Packet_Loss_Rate","Real_LinkMargin_dB", "EbNo_dB", "Range_km","BER"
            ]

            final_cols = [c for c in header if c in df.columns]
            df.to_csv(self.LINK_RESULT_PATH, index=False, encoding="utf-8-sig", columns=final_cols)
            print(f"✅ 数据已保存至: {self.LINK_RESULT_PATH} (共 {len(df)} 条记录)")
            print(f"   📊 包含指标: Latency, Bandwidth(QPSK Std), PLR")
        else:
            print("\n⚠️ 依然未获取到数据。")
            if error_count > 0:
                print(f"⚠️ 过程中捕获了 {error_count} 次错误，请检查上方的错误日志。")

    """导出所有卫星在整个场景时间内的 J2000 笛卡尔坐标"""

    def export_sat_positions(self, step):
        print("\n📍 导出卫星位置...")
        scenario2 = self.scenario.QueryInterface(STKObjects.IAgScenario)
        start_time_str = scenario2.StartTime
        stop_time_str = scenario2.StopTime

        start_dt = datetime.datetime.strptime(start_time_str, "%d %b %Y %H:%M:%S.%f")
        stop_dt = datetime.datetime.strptime(stop_time_str, "%d %b %Y %H:%M:%S.%f")

        # 如果你希望用 step 参数控制采样步长（秒），就用它来算循环次数
        total_seconds = (stop_dt - start_dt).total_seconds()
        # 从开始到结束，每step采集一次卫星位置，共采集多少次
        n_slots = int(total_seconds / step)

        # 确保至少有一个时间点
        if n_slots == 0: n_slots = 1

        all_rows = []

        # 遍历所有卫星
        for name, sat in tqdm(self.sat_dict.items(), desc="导出卫星坐标", file=sys.stdout, ncols=100):
            try:
                result = sat.DataProviders.GetDataPrvTimeVarFromPath("Cartesian Position//J2000")
            except Exception as e:
                print(f"⚠️ 获取 Cartesian Position TimeVar 出错: {name}: {e}")
                continue

            X_List = []
            Y_List = []
            Z_List = []
            Time_List = []
            for k in range(n_slots):
                slot_start = (start_dt + datetime.timedelta(seconds=step * k)).strftime("%d %b %Y %H:%M:%S.%f")[:-3]
                slot_stop = (start_dt + datetime.timedelta(seconds=step * (k + 1))).strftime("%d %b %Y %H:%M:%S.%f")[
                            :-3]

                try:
                    slot_result = result.ExecElements(
                        slot_start,
                        slot_stop,
                        StepTime=step,  # 从start到stop这段时间，每隔step秒输出一个数据点
                        ElementNames=["Time", "x", "y", "z"]
                    )
                except Exception as e:
                    print(f"⚠️ ExecElements 计算位置出错: {name}: {e}")
                    continue

                try:
                    times = slot_result.DataSets.GetDataSetByName('Time').GetValues()
                    xs = slot_result.DataSets.GetDataSetByName('x').GetValues()
                    ys = slot_result.DataSets.GetDataSetByName('y').GetValues()
                    zs = slot_result.DataSets.GetDataSetByName('z').GetValues()
                except Exception as e:
                    print(f"⚠️ 读取位置数据集出错: {name}: {e}")
                    continue

                if not times:
                    continue

                Time_List.append(times[0])
                X_List.append(xs[0])
                Y_List.append(ys[0])
                Z_List.append(zs[0])

            # 写入总列表
            for t, x, y, z in zip(Time_List, X_List, Y_List, Z_List):
                all_rows.append({
                    "TimeString": t,
                    "Sat": name,
                    "x_km": x,
                    "y_km": y,
                    "z_km": z,
                })

        if all_rows:
            df = pd.DataFrame(all_rows)
            out_path = os.path.join(self.DATA_DIR, "sat_positions.csv")
            header = [
                "TimeString（时间）",
                "Sat（卫星名称）",
                "x_km（J2000坐标X，km）",
                "y_km（J2000坐标Y，km）",
                "z_km（J2000坐标Z，km）",
            ]
            df.to_csv(out_path, index=False, encoding="utf-8-sig", header=header)
            print(f"✅ 卫星位置已导出: {out_path}({len(df)} 行)")
        else:
            print("⚠️ 未导出任何卫星位置数据。")

    def export_isl_design_pairs(self):
        isl_pairs = self._generate_unique_isl_pairs()
        if not isl_pairs:
            print("⚠️ 未生成任何 ISL 设计对")
            return

        rows = [{"Src": a, "Dst": b} for a, b in sorted(isl_pairs)]
        df = pd.DataFrame(rows)
        out_path = os.path.join(self.DATA_DIR, "isl_design_pairs.csv")
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"✅ ISL 设计拓扑已导出: {out_path} (共 {len(df)} 条)")

    """执行完整流程"""

    def run_full_simulation(self):
        """运行完整仿真流程"""
        print("\n" + "=" * 60)
        print("🛰️  STK 星链星座仿真")
        print("=" * 60)
        self.create_walker_constellation()
        self.sat_dict = self.get_existing_satellites()
        self.setup_transceivers()
        self.setup_isl_links()
        self.export_isl_design_pairs()
        self.export_link_status_time_series(step=self.STEP)
        self.export_sat_positions(step=self.STEP)
        print("\n" + "=" * 60)
        print("✅ STK仿真完成")
        print("=" * 60)
# ==================== 主程序入口 ====================
if __name__ == "__main__":
    manager = StarlinkConstellationManager()
    manager.run_full_simulation()
