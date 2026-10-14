"""
A股智能体分析系统 - 主程序入口
支持命令行模式和API模式
"""

import argparse
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from simple_autogen.astock_autogen_system import AStockAutoGenSystem


def analyze_stock(symbol: str, api_key: str, output_file: str = None):
    """
    分析单只股票

    Args:
        symbol: 股票代码
        api_key: MiniMax API密钥
        output_file: 输出文件路径（可选）
    """
    print(f"\n{'='*60}")
    print(f"开始分析A股股票: {symbol}")
    print(f"{'='*60}\n")

    # 创建系统实例
    system = AStockAutoGenSystem(api_key)

    # 执行分析
    result = system.analyze_stock(symbol)

    # 输出结果
    if 'error' in result:
        print(f"错误: {result['error']}")
        return

    print(f"\n{'='*60}")
    print(f"股票分析报告: {result['name']} ({result['symbol']})")
    print(f"{'='*60}")

    print(f"\n【基本信息】")
    print(f"  股票代码: {result['symbol']}")
    print(f"  股票名称: {result['name']}")
    print(f"  当前价格: {result['price']}元")
    print(f"  所属行业: {result['industry']}")
    print(f"  分析时间: {result['analysis_date']}")

    print(f"\n【财务指标】")
    fm = result['financial_metrics']
    for key, value in fm.items():
        print(f"  {key}: {value}")

    print(f"\n【风险指标】")
    rm = result['risk_metrics']
    for key, value in rm.items():
        print(f"  {key}: {value}")

    print(f"\n【数据分析】")
    print(result['data_analysis'][:500] + "..." if len(result['data_analysis']) > 500 else result['data_analysis'])

    print(f"\n【财务分析】")
    print(result['financial_analysis'][:500] + "..." if len(result['financial_analysis']) > 500 else result['financial_analysis'])

    print(f"\n【风险分析】")
    print(result['risk_analysis'][:500] + "..." if len(result['risk_analysis']) > 500 else result['risk_analysis'])

    print(f"\n【投资建议】")
    print(result['investment_advice'])

    print(f"\n{'='*60}")
    print(f"AutoGen多智能体协作分析完成")
    print(f"{'='*60}\n")

    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {output_file}")


def interactive_mode(api_key: str):
    """
    交互式模式

    Args:
        api_key: MiniMax API密钥
    """
    print("\n欢迎使用A股智能体分析系统")
    print("输入股票代码进行分析（如 000001），输入 q 退出\n")

    system = AStockAutoGenSystem(api_key)

    while True:
        symbol = input("请输入股票代码: ").strip()

        if symbol.lower() == 'q':
            print("感谢使用，再见！")
            break

        if not symbol:
            continue

        # 规范化股票代码
        if len(symbol) == 6:
            symbol = symbol  # 假设是深交所或上交所
        else:
            print("股票代码应为6位数字")
            continue

        analyze_stock(symbol, api_key)


def main():
    parser = argparse.ArgumentParser(description='A股智能体分析系统')
    parser.add_argument('--symbol', '-s', type=str, help='股票代码（如 000001）')
    parser.add_argument('--api-key', '-k', type=str, help='MiniMax API密钥')
    parser.add_argument('--output', '-o', type=str, help='输出文件路径')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互式模式')

    args = parser.parse_args()

    # API密钥
    api_key = args.api_key
    if not api_key:
        # 尝试从配置文件读取
        import yaml
        config_path = Path(__file__).parent.parent / 'config.yaml'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                api_key = config.get('minimax', {}).get('api_key', '')

    if not api_key:
        print("错误: 请提供MiniMax API密钥")
        print("可以通过 --api-key 参数或 config.yaml 配置文件提供")
        return

    if args.interactive:
        interactive_mode(api_key)
    elif args.symbol:
        analyze_stock(args.symbol, api_key, args.output)
    else:
        # 默认进入交互模式
        interactive_mode(api_key)


if __name__ == '__main__':
    main()