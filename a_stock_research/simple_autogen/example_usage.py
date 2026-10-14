"""
A股智能体分析系统 - 使用示例

这个示例展示如何使用A股智能体分析系统对股票进行分析
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from simple_autogen.astock_autogen_system import AStockAutoGenSystem


def example_basic_usage():
    """基本使用示例"""
    # MiniMax API密钥
    api_key = "sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY"

    # 创建系统实例
    system = AStockAutoGenSystem(api_key)

    # 分析股票 - 以平安银行(000001)为例
    symbol = "000001"
    print(f"开始分析股票: {symbol}")

    result = system.analyze_stock(symbol)

    # 打印结果
    print("\n" + "="*60)
    print(f"股票: {result['name']} ({result['symbol']})")
    print(f"分析时间: {result['analysis_date']}")
    print("="*60)

    print("\n【投资建议】")
    print(result.get('investment_advice', 'N/A')[:500])


def example_batch_analysis():
    """批量分析示例"""
    api_key = "sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY"

    system = AStockAutoGenSystem(api_key)

    # 股票列表
    stocks = [
        "000001",  # 平安银行
        "600519",  # 贵州茅台
        "000002",  # 万科A
        "600036",  # 招商银行
    ]

    print("批量分析A股股票...")
    print("="*60)

    for symbol in stocks:
        print(f"\n分析 {symbol}...")
        result = system.analyze_stock(symbol)
        print(f"  {result['name']}: {result.get('investment_advice', 'N/A')[:100]}...")

    print("\n批量分析完成!")


if __name__ == '__main__':
    print("示例1: 基本使用")
    print("-"*40)
    # example_basic_usage()

    print("\n\n示例2: 批量分析")
    print("-"*40)
    # example_batch_analysis()

    print("\n请取消上面示例的注释来运行")