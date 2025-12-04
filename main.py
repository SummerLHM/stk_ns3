"""
@Author   : wwq
@Date     ：2025/11/25
@Function :
            STK-NS3 联合仿真系统 - 主程序入口

            功能:
            1. STK星座仿真: 创建Walker-Star星座，配置ISL链路
            2. 数据转换: 提取链路参数（时延、带宽、丢包率）
            3. 时间片管理: 划分时间片，生成虚拟拓扑
            4. NS3网络仿真: 最短路径路由，多跳转发
            5. 结果分析: 汇总时延、吞吐量、丢包率
"""

import sys
print(f"当前 Python 路径: {sys.executable}")
import argparse
from datetime import datetime


def check_stk_available() -> bool:
    """检查STK是否可用"""
    try:
        from comtypes.client import GetActiveObject
        return True
    except ImportError:
        return False


def run_stk_simulation():
    """运行STK仿真"""
    print("\n" + "=" * 60)
    print("阶段 1: STK 星座仿真")
    print("=" * 60)

    if not check_stk_available():
        print("❌ STK环境不可用")
        print("   请安装comtypes: pip install comtypes")
        print("   并确保STK已正确安装")
        return False

    try:
        from starlink_stk_manager import StarlinkConstellationManager

        manager = StarlinkConstellationManager()
        manager.run_full_simulation()
        return True

    except Exception as e:
        print(f"❌ STK仿真失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_data_conversion(use_time_slices: bool = False,
                        slice_duration: float = 60.0,
                        num_demands: int = 10,
                        demand_type: str = "mixed"):
    """
    运行数据转换

    Args:
        use_time_slices: 是否使用时间片模式
        slice_duration: 时间片时长（秒）
        num_demands: 流量需求数量
        demand_type: 流量类型 ("random", "intra_orbit", "inter_orbit", "mixed")
    """
    print("\n" + "=" * 60)
    print("阶段 2: 数据转换 (STK → NS3)")
    print("=" * 60)

    try:
        from stk_ns3_bridge import STKNS3Bridge

        bridge = STKNS3Bridge(config_file="ns3_config.json")

        if not bridge.load_stk_data():
            print("❌ 加载STK数据失败")
            return False

        bridge.build_topology()
        bridge.export_for_ns3()
        bridge.sync_to_shared_folder()
        bridge.print_summary()

        # 如果使用时间片模式，额外生成时间片和流量需求
        if use_time_slices:
            print("\n" + "-" * 60)
            print("生成时间片和流量需求...")
            print("-" * 60)

            from time_slice_manager import TimeSliceManager

            ts_manager = TimeSliceManager(slice_duration_sec=slice_duration)
            ts_manager.load_stk_data("data/link_status.csv")
            ts_manager.create_time_slices()

            for i in range(len(ts_manager.time_slices)):
                ts_manager.build_topology_for_slice(i)

            ts_manager.generate_traffic_demands(
                num_demands=num_demands,
                demand_type=demand_type
            )
            ts_manager.export_for_ns3()
            ts_manager.print_summary()

        return True

    except Exception as e:
        print(f"❌ 数据转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_analysis(use_mock: bool = False):
    """运行结果分析"""
    print("\n" + "=" * 60)
    print("阶段 3: NS3 结果分析")
    print("=" * 60)

    try:
        from ns3_runner import NS3SimulationManager

        manager = NS3SimulationManager(config_file="ns3_config.json")

        if use_mock or not manager.check_results_available():
            if not use_mock:
                print("⚠️ NS3结果不可用")
                choice = input("\n是否生成模拟数据进行测试? (y/n): ")
                if choice.lower() != 'y':
                    return False
            manager.generate_mock_results()

        manager.analyze_results()
        return True

    except Exception as e:
        print(f"❌ 结果分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_workflow():
    """打印工作流程"""
    print("""
            STK-NS3 联合仿真工作流程                     
==================================================
Windows端（PyCharm）：
--------------------------------------------------
1. python main.py --mode stk                           
        → 运行STK仿真，生成链路数据                         
2. python main.py --mode prepare-ns3                    
        → 转换数据，准备NS3输入文件                         
    或使用时间片模式:                                    
    python main.py --mode prepare-ns3 --time-slices      
        --slice-duration 60 --num-demands 10             
        
        
Linux端 (终端):                                           
----------------------------------------------------
3. cd /repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink 
    bash run.sh                                         
        → 运行NS3仿真（支持最短路径路由）                   
        
        
Windows端 (PyCharm):                                     
-----------------------------------------------------
4. python main.py --mode analysis                      
    → 分析NS3结果，生成报告                             
""")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="STK-NS3 联合仿真系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  full         完整流程 (STK → 数据转换 → 等待NS3 → 分析)
  stk          仅运行STK仿真
  prepare-ns3  准备NS3数据（支持时间片模式）
  analysis     分析NS3结果
  test         使用模拟数据测试
  workflow     显示工作流程

时间片选项 (用于 prepare-ns3 模式):
  --time-slices         启用时间片模式
  --slice-duration SEC  时间片时长，默认60秒
  --num-demands NUM     流量需求数量，默认10
  --demand-type TYPE    流量类型: random/intra_orbit/inter_orbit/mixed

示例:
  python main.py --mode full
  python main.py --mode prepare-ns3 --time-slices --num-demands 20
  python main.py --mode prepare-ns3 --time-slices --demand-type inter_orbit
        """
    )

    parser.add_argument(
        '--mode',
        choices=['full', 'stk', 'prepare-ns3', 'analysis', 'test', 'workflow'],
        default='workflow',
        help='运行模式'
    )

    parser.add_argument(
        '--skip-stk',
        action='store_true',
        help='跳过STK仿真（使用现有数据）'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='ns3_config.json',
        help='配置文件路径'
    )

    # 时间片相关参数
    parser.add_argument(
        '--time-slices',
        action='store_true',
        help='启用时间片模式'
    )

    parser.add_argument(
        '--slice-duration',
        type=float,
        default=60.0,
        help='时间片时长（秒），默认60'
    )

    parser.add_argument(
        '--num-demands',
        type=int,
        default=20,
        help='流量需求数量，默认20'
    )

    parser.add_argument(
        '--demand-type',
        choices=['random', 'intra_orbit', 'inter_orbit', 'mixed'],
        default='mixed',
        help='流量类型，默认mixed'
    )

    args = parser.parse_args()

    # 打印标题
    print("\n" + "=" * 60)
    print("🛰️  STK-NS3 联合仿真系统")
    print("=" * 60)
    print(f"运行模式: {args.mode}")
    print(f"配置文件: {args.config}")
    if args.time_slices:
        print(f"时间片模式: 启用")
        print(f"  时间片时长: {args.slice_duration} 秒")
        print(f"  流量需求数: {args.num_demands}")
        print(f"  流量类型: {args.demand_type}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 执行相应模式
    if args.mode == 'workflow':
        print_workflow()
        return

    if args.mode == 'full':
        if not args.skip_stk:
            if not run_stk_simulation():
                print("\n⚠️ STK仿真失败，尝试使用现有数据...")

        if run_data_conversion(
                use_time_slices=args.time_slices,
                slice_duration=args.slice_duration,
                num_demands=args.num_demands,
                demand_type=args.demand_type
        ):
            print("\n" + "=" * 60)
            print("⏳ 请在Linux端运行NS3仿真")
            print("=" * 60)
            print("""
操作步骤:
1. 打开Linux终端
2. 执行: cd /repos_ns3/ns-3-allinone/ns-3.45/scratch/starlink
3. 执行: bash run.sh
4. 等待仿真完成
5. 返回Windows运行: python main.py --mode analysis
""")

    elif args.mode == 'stk':
        run_stk_simulation()

    elif args.mode == 'prepare-ns3':
        run_data_conversion(
            use_time_slices=args.time_slices,
            slice_duration=args.slice_duration,
            num_demands=args.num_demands,
            demand_type=args.demand_type
        )

    elif args.mode == 'analysis':
        run_analysis(use_mock=False)

    elif args.mode == 'test':
        run_analysis(use_mock=True)

    # 完成
    print("\n" + "=" * 60)
    print("✅ 操作完成")
    print("=" * 60)

    print("\n📁 文件位置:")
    print("   data/           - STK输出数据")
    print("   ns3_input/      - NS3输入数据")
    if args.time_slices:
        print("     - link_params.csv       链路参数")
        print("     - traffic_demands.csv   流量需求")
        print("     - time_slices.json      时间片信息")
    print("   ns3_results/    - NS3仿真结果")


if __name__ == "__main__":
    main()
