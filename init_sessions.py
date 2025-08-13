#!/usr/bin/env python3
"""
初始化会话管理器
从现有的配置文件导入会话数据到会话管理器
"""

import json
import logging
from session_manager import session_manager, SessionMode

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_model_endpoint_map():
    """从 model_endpoint_map.json 加载模型到端点的映射"""
    try:
        with open('model_endpoint_map.json', 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
    except FileNotFoundError:
        logger.warning("'model_endpoint_map.json' 文件未找到")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"解析 'model_endpoint_map.json' 失败: {e}")
        return {}

def load_config():
    """从 config.jsonc 加载配置"""
    import re
    try:
        with open('config.jsonc', 'r', encoding='utf-8') as f:
            content = f.read()
            # 移除注释
            json_content = re.sub(r'//.*', '', content)
            json_content = re.sub(r'/\*.*?\*/', '', json_content, flags=re.DOTALL)
            return json.loads(json_content)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"加载 'config.jsonc' 失败: {e}")
        return {}

def main():
    """主函数：初始化会话管理器"""
    logger.info("开始初始化会话管理器...")
    
    # 加载现有配置
    config = load_config()
    model_endpoint_map = load_model_endpoint_map()
    
    # 导入默认会话
    if config.get('session_id') and config.get('message_id'):
        default_session = session_manager.create_session(
            name="Default Session",
            mode=SessionMode.DIRECT_CHAT,
            session_id=config['session_id'],
            message_id=config['message_id'],
            metadata={'source': 'config.jsonc', 'default': True}
        )
        session_manager.set_default_session(default_session.session_id)
        logger.info(f"已导入默认会话: {default_session.name}")
    
    # 导入模型端点映射中的会话
    if model_endpoint_map:
        session_manager.import_from_model_endpoint_map(model_endpoint_map)
        logger.info(f"已从 model_endpoint_map.json 导入会话")
    
    # 显示统计信息
    stats = session_manager.get_session_stats()
    logger.info(f"会话管理器初始化完成:")
    logger.info(f"  - 总会话数: {stats['total_sessions']}")
    logger.info(f"  - 活跃会话: {stats['active_sessions']}")
    logger.info(f"  - 错误会话: {stats['error_sessions']}")
    
    # 列出所有会话
    sessions = session_manager.list_sessions()
    for session in sessions:
        logger.info(f"  - {session.name} ({session.session_id[:8]}...) - {session.mode.value}")
        if session.battle_target:
            logger.info(f"    战斗目标: {session.battle_target}")

if __name__ == "__main__":
    main()