"""
@Author   : wwq
@Date     : 2025/11/25
@Function : STK-NS3 联合仿真系统 - 主程序入口
"""

import argparse
from datetime import datetime


def run_stk_simulation():
    """运行STK仿真"""
    print("\n" + "=" * 60)
    print("阶段 1: STK 星座仿真")
    print("=" * 60)

    try:
        from comtypes.client import GetActiveObject
    except ImportError:
        print("❌ 请安装comtypes: pip install comtypes")
        return False

    try:
        from starlink_stk_manager import StarlinkConstellationManager
        manager = StarlinkConstellationManager()
        manager.run_full_simulation()
        return True
    except Exception as e:
        print(f"❌ STK仿真失败: {e}")
        return False


def run_data_conversion(slice_duration: float, num_demands: int, demand_type: str):
    """运行数据转换"""
    print("\n" + "=" * 60)
    print("阶段 2: 数据转换 (STK → NS3)")
    print("=" * 60)

    try:
        from time_slice_manager import TimeSliceManager
        print(f"⚙️ 配置: 切片时长={slice_duration}s, 流量需求={num_demands}, 类型={demand_type}")

        ts_manager = TimeSliceManager(slice_duration_sec=slice_duration)

        if not ts_manager.load_stk_data("data/link_status.csv"):
            print("❌ 加载STK数据失败")
            return False

        ts_manager.create_time_slices()

        for i in range(len(ts_manager.time_slices)):
            ts_manager.build_topology_for_slice(i)

        ts_manager.generate_traffic_demands(num_demands=num_demands, demand_type=demand_type)
        ts_manager.export_for_ns3()
        ts_manager.print_summary()
        return True
    except Exception as e:
        print(f"❌ 数据转换失败: {e}")
        return False


def run_analysis():
    """运行结果分析"""
    print("\n" + "=" * 60)
    print("阶段 3: NS3 结果分析")
    print("=" * 60)

    try:
        from ns3_runner import NS3SimulationManager
        manager = NS3SimulationManager(config_file="ns3_config.json")

        if not manager.check_results_available():
            print("⚠️ NS3结果不可用")
            return False

        manager.analyze_results()
        return True
    except Exception as e:
        print(f"❌ 结果分析失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="STK-NS3 联合仿真系统")

    parser.add_argument('--mode', choices=['stk', 'prepare-ns3', 'analysis'],
                        required=True, help='运行模式')
    parser.add_argument('--time-slices', action='store_true', help='启用时间片模式（默认启用，可省略）')
    parser.add_argument('--slice-duration', type=float, default=60.0, help='时间片时长（秒）')
    parser.add_argument('--num-demands', type=int, default=20, help='流量需求数量')
    parser.add_argument('--demand-type', choices=['random', 'intra_orbit', 'inter_orbit', 'mixed'],
                        default='mixed', help='流量类型')

    args = parser.parse_args()

    print(f"\n🛰️ STK-NS3 联合仿真 | 模式: {args.mode} | {datetime.now().strftime('%H:%M:%S')}")

    if args.mode == 'stk':
        run_stk_simulation()
    elif args.mode == 'prepare-ns3':
        run_data_conversion(args.slice_duration, args.num_demands, args.demand_type)
    elif args.mode == 'analysis':
        run_analysis()

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
