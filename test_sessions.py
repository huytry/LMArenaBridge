#!/usr/bin/env python3
"""
测试会话管理系统
验证会话创建、更新、统计等功能
"""

import json
import time
from datetime import datetime
from session_manager import session_manager, SessionMode, SessionStatus

def test_session_creation():
    """测试会话创建"""
    print("🧪 测试会话创建...")
    
    # 创建测试会话
    session1 = session_manager.create_session(
        name="Test Direct Chat",
        mode=SessionMode.DIRECT_CHAT,
        metadata={'test': True, 'type': 'direct_chat'}
    )
    
    session2 = session_manager.create_session(
        name="Test Battle A",
        mode=SessionMode.BATTLE,
        battle_target="A",
        metadata={'test': True, 'type': 'battle_a'}
    )
    
    session3 = session_manager.create_session(
        name="Test Battle B",
        mode=SessionMode.BATTLE,
        battle_target="B",
        metadata={'test': True, 'type': 'battle_b'}
    )
    
    print(f"✅ 创建了 {len([session1, session2, session3])} 个测试会话")
    return [session1, session2, session3]

def test_session_activity():
    """测试会话活动更新"""
    print("🧪 测试会话活动更新...")
    
    sessions = session_manager.list_sessions()
    if not sessions:
        print("❌ 没有会话可测试")
        return
    
    # 更新会话活动
    for i, session in enumerate(sessions[:3]):  # 只测试前3个
        success = i % 2 == 0  # 交替成功和失败
        error_msg = "Test error" if not success else None
        
        session_manager.update_session_activity(
            session.session_id,
            success=success,
            error_message=error_msg
        )
        
        print(f"  更新会话 {session.name}: {'成功' if success else '失败'}")
    
    print("✅ 会话活动更新完成")

def test_session_stats():
    """测试会话统计"""
    print("🧪 测试会话统计...")
    
    stats = session_manager.get_session_stats()
    print(f"  总会话数: {stats['total_sessions']}")
    print(f"  活跃会话: {stats['active_sessions']}")
    print(f"  错误会话: {stats['error_sessions']}")
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  总错误数: {stats['total_errors']}")
    print(f"  错误率: {stats['error_rate']:.1f}%")
    
    print("✅ 会话统计正常")

def test_session_operations():
    """测试会话操作"""
    print("🧪 测试会话操作...")
    
    sessions = session_manager.list_sessions()
    if not sessions:
        print("❌ 没有会话可测试")
        return
    
    # 测试获取会话
    test_session = sessions[0]
    retrieved_session = session_manager.get_session(test_session.session_id)
    if retrieved_session:
        print(f"  ✅ 成功获取会话: {retrieved_session.name}")
    
    # 测试设置默认会话
    if session_manager.set_default_session(test_session.session_id):
        print(f"  ✅ 成功设置默认会话: {test_session.name}")
    
    # 测试获取默认会话
    default_session = session_manager.get_default_session()
    if default_session:
        print(f"  ✅ 默认会话: {default_session.name}")
    
    print("✅ 会话操作测试完成")

def test_session_export():
    """测试会话导出"""
    print("🧪 测试会话导出...")
    
    export_data = session_manager.export_sessions()
    print(f"  导出了 {len(export_data)} 个会话组")
    
    for session_name, mappings in export_data.items():
        print(f"    {session_name}: {len(mappings)} 个映射")
    
    print("✅ 会话导出正常")

def test_session_cleanup():
    """测试会话清理"""
    print("🧪 测试会话清理...")
    
    initial_count = len(session_manager.list_sessions())
    
    # 创建一些测试会话用于清理
    for i in range(3):
        session_manager.create_session(
            name=f"Cleanup Test {i}",
            mode=SessionMode.DIRECT_CHAT,
            metadata={'cleanup_test': True}
        )
    
    # 清理测试会话
    session_manager.cleanup_idle_sessions(max_idle_hours=0)  # 立即清理
    
    final_count = len(session_manager.list_sessions())
    print(f"  清理前: {initial_count} 个会话")
    print(f"  清理后: {final_count} 个会话")
    
    print("✅ 会话清理测试完成")

def cleanup_test_sessions():
    """清理测试会话"""
    print("🧹 清理测试会话...")
    
    sessions = session_manager.list_sessions()
    test_sessions = [s for s in sessions if s.metadata.get('test') or s.metadata.get('cleanup_test')]
    
    for session in test_sessions:
        session_manager.delete_session(session.session_id)
        print(f"  删除测试会话: {session.name}")
    
    print(f"✅ 清理了 {len(test_sessions)} 个测试会话")

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 LMArena Session Manager 测试")
    print("=" * 60)
    
    try:
        # 运行测试
        test_sessions = test_session_creation()
        test_session_activity()
        test_session_stats()
        test_session_operations()
        test_session_export()
        test_session_cleanup()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理测试数据
        cleanup_test_sessions()
        
        # 显示最终统计
        stats = session_manager.get_session_stats()
        print(f"\n📊 最终统计: {stats['total_sessions']} 个会话")

if __name__ == "__main__":
    main()