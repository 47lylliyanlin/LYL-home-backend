"""
记忆系统维护脚本
- 自动归档低分记忆
- 强化常用记忆
"""

from api.memory import memory_system
from datetime import datetime, timedelta

def maintain_memories(score_threshold: float = 2.0):
    """
    维护记忆系统

    Args:
        score_threshold: 归档阈值，低于此分数的dynamic记忆会被归档
    """
    print("开始维护记忆系统...")

    # 1. 归档低分记忆
    print(f"\n1. 归档低分记忆（阈值={score_threshold}）")
    memory_system.archive_old_memories(score_threshold)

    # 2. 强化高频记忆
    print("\n2. 强化高频记忆")
    memories = memory_system.load_all_memories()

    for memory in memories:
        # 使用次数超过10次的，提升importance
        if memory.use_count > 10 and memory.importance < 10:
            old_importance = memory.importance
            memory.importance = min(memory.importance + 1, 10)
            memory_system.save_memory(memory)
            print(f"强化记忆 {memory.id}: importance {old_importance} → {memory.importance}")

    # 3. 统计信息
    print("\n3. 记忆统计")
    all_memories = memory_system.load_all_memories(include_archive=True)

    stats = {
        'permanent': 0,
        'dynamic': 0,
        'feel': 0,
        'archive': 0
    }

    for memory in all_memories:
        stats[memory.type] = stats.get(memory.type, 0) + 1

    print(f"Permanent: {stats['permanent']}")
    print(f"Dynamic: {stats['dynamic']}")
    print(f"Feel: {stats['feel']}")
    print(f"Archive: {stats['archive']}")
    print(f"Total: {len(all_memories)}")

    print("\n维护完成！")

if __name__ == "__main__":
    maintain_memories()
