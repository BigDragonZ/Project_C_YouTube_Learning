#!/usr/bin/env python3
"""
Batch chapter generation for Principles of Macroeconomics.
Generates remaining chapters (03-14) via NotebookLM ask.
"""
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
NOTEBOOK_ID = "1e3c57c7-ff61-48b9-a8e1-8c74a122cd30"

CHAPTERS = [
    ("03", "03", "交换的福利效应与分工逻辑", "Chapter 3: The Gains From Trade"),
    ("04", "04-05", "市场均衡机制与价格发现", "Chapter 4: Supply and Demand"),
    ("05", "07", "国民收入的核算体系及其局限", "Chapter 23: Measuring the Income of a Nation"),
    ("06", "08", "生活成本的跨期评估与通货膨胀", "Chapter 24: Measuring the Cost of Living"),
    ("07", "09", "全要素生产率与长期增长动力", "Chapter 25: Production and Growth"),
    ("08", "10", "跨期资源配置：储蓄、投资与金融中介", "Chapter 26: Saving, Investment and the Financial System"),
    ("09", "11", "劳动力市场的摩擦与结构性失业", "Chapter 28: Unemployment"),
    ("10", "12", "现代货币体系与央行职能", "Chapter 29: The Monetary System"),
    ("11", "13", "长期通胀的货币性质与社会成本", "Chapter 30: Money Growth and Inflation"),
    ("12", "06", "开放宏观经济与贸易政策博弈", "Chapter 9: International Trade"),
    ("13", "14", "短期经济波动：总需求-总供给模型", "Chapter 33: Aggregate Demand and Aggregate Supply"),
    ("14", "15", "货币与财政政策的传导与综合治理", "Chapter 34: The Influence of Monetary and Fiscal Policy"),
]

PROMPT_TEMPLATE = """基于视频{video_range}的内容（{english_title}），请深入分析本章，输出必须为中文：

1. 核心概念的数学定义与分类
2. 关键公式的完整推导过程
3. 理论的边界条件与假设
4. 用具体案例说明原理如何在现实中体现
5. 学术批判：这些原理的局限性与反例
6. 跨章节关联：与后续章节的逻辑联系

要求：研究生级别技术密度，所有内容用中文输出（专业术语保留英文），署名DALONG ZHANG。"""

def generate_chapter(num: str, video_range: str, title: str, english_title: str):
    """Generate a single chapter via NotebookLM."""
    prompt = PROMPT_TEMPLATE.format(
        video_range=video_range,
        english_title=english_title
    )
    
    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "notebooklm"),
        "ask", "--notebook", NOTEBOOK_ID,
        prompt
    ]
    
    print(f"\n{'='*60}")
    print(f"Generating Ch.{num}: {title}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        print(f"[ERROR] Ch.{num} failed: {result.stderr[:200]}")
        return False
    
    # Extract answer content
    content = result.stdout
    if "Answer:" in content:
        content = content.split("Answer:", 1)[1].strip()
    
    # Save to file
    out_dir = PROJECT_ROOT / "output" / "Principles_of_Macroeconomics"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"Ch_{num}_{title}.md"
    filepath = out_dir / filename
    
    # Add metadata header
    header = f"""# Ch.{num} {title}

> **Metadata**
> - 署名：DALONG ZHANG
> - 课程：Principles of Macroeconomics
> - 视频范围：{video_range}
> - 核心命题：[从NotebookLM输出中提取]
> - 关联笔记：[待补充]

---

"""
    
    filepath.write_text(header + content, encoding="utf-8")
    print(f"[OK] Saved: {filepath}")
    return True

def main():
    for num, video_range, title, english_title in CHAPTERS:
        success = generate_chapter(num, video_range, title, english_title)
        if not success:
            print(f"[WARN] Stopping at Ch.{num} due to error")
            break
        time.sleep(2)  # Rate limiting
    
    print("\n[OK] Batch generation complete")

if __name__ == "__main__":
    main()
