#!/usr/bin/env python3
"""
Claude Code GrowthBook Feature Flags Dumper

Extracts feature flags configuration from Claude Code's GrowthBook remote eval endpoint.
Works on macOS and Linux where Claude Code is installed.

Usage:
    python3 claude_features.py              # Pretty print
    python3 claude_features.py --json       # Raw JSON output
    python3 claude_features.py --experiments # Only show A/B experiments
"""

import json
import os
import platform
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

GROWTHBOOK_CLIENT_KEY = "sdk-zAZezfDKGoZuXXKe"
GROWTHBOOK_API_HOST = "https://api.anthropic.com"

# 功能标志中文说明 + 分类（通过逆向分析 Claude Code CLI 和 Desktop 二进制得出）
# 标注 [Desktop] 表示仅在桌面端使用，CLI 二进制中未引用

FLAG_DESCRIPTIONS = {
    # ── 总开关/元信息 ──
    "auto_migrate_to_native":       "自动将 npm 安装迁移到原生二进制安装方式",
    "ccr_auto_permission_mode":     "Claude Code Remote 自动权限模式",
    "tengu-off-switch":             "紧急关闭开关，激活后阻止非首方订阅用户发 API 请求",
    "tengu-top-of-feed-tip":        "在对话顶部显示使用提示/建议信息",
    # ── 遥测/事件上报 ──
    "tengu_1p_event_batch_config":  "第一方事件日志批量上报配置（批次大小、间隔、队列上限）",
    "tengu_event_sampling_config":  "遥测事件采样率配置",
    "tengu_log_datadog_events":     "将事件日志发送到 Datadog 监控平台",
    "tengu_trace_lantern":          "启用分布式追踪（trace）功能",
    "tengu_ant_attribution_header_new": "新版 Anthropic 归因请求头",
    "tengu_attribution_header":     "API 请求中添加归因（attribution）请求头",
    "tengu_frond_boric":            "按事件名称的细粒度功能开关映射",
    # ── 插件/Agent Teams (Amber) ──
    "tengu_amber_flint":            "Agent Teams（多智能体协作）功能总开关",
    "tengu_amber_lattice":          "Agent Teams 可用插件列表配置",
    "tengu_amber_prism":            "Agent Teams 权限拒绝提示文案增强",
    "tengu_amber_quartz":           "模型选择器功能开关",
    "tengu_amber_stoat":            "Agent Teams 子功能开关",
    "tengu_amber_wren":             "文件读取工具的最大文件大小和 token 数限制",
    # ── 插件市场 (Harbor) ──
    "tengu_harbor":                 "插件市场（Harbor）功能总开关",
    "tengu_harbor_ledger":          "插件市场注册表（可用插件列表）",
    "tengu_harbor_permissions":     "插件市场权限控制",
    "tengu_lapis_finch":            "插件推荐提示（根据项目类型推荐相关插件）",
    "tengu_plugin_official_mkt_git_fallback": "官方插件市场下载失败时回退到 Git 克隆",
    "tengu_gha_plugin_code_review": "GitHub Actions 中的插件代码审查",
    # ── Bridge/桌面端通信 ──
    "tengu_bridge_min_version":             "Bridge（桌面端通信桥）最低版本要求",
    "tengu_bridge_poll_interval_config":    "Bridge 轮询间隔详细配置",
    "tengu_bridge_poll_interval_ms":        "Bridge 轮询间隔毫秒数",
    "tengu_bridge_repl_v2":                 "Bridge REPL v2 版本开关",
    "tengu_bridge_repl_v2_config":          "Bridge REPL v2 详细配置（重试/超时/心跳）",
    "tengu_copper_bridge":                  "WebSocket Bridge 连接（bridge.claudeusercontent.com）",
    # ── CCR (Claude Code Remote) ──
    "tengu_ccr_bridge":               "Claude Code Remote 远程控制功能开关",
    "tengu_ccr_bridge_multi_session":  "Claude Code Remote 多会话支持",
    "tengu_ccr_bundle_max_bytes":      "CCR Git bundle 最大字节数限制",
    "tengu_ccr_bundle_seed_enabled":   "CCR 启动时自动上传 Git bundle 种子",
    "tengu_quartz_lantern":            "远程模式（CLAUDE_CODE_REMOTE）特定功能",
    # ── 模型/推理 ──
    "tengu_opus_default_pro_plan":     "Pro 计划用户默认使用 Opus 模型",
    "tengu_immediate_model_command":   "立即执行 /model 切换模型（无需确认）",
    "tengu_auto_mode_config":          "Auto Mode（自动权限模式）配置",
    "tengu_crystal_beam":              "思考预算 token 配置（budgetTokens）",
    "tengu_turtle_carbon":             "Ultrathink（超级深度推理）功能开关",
    "tengu_thinkback":                 "思考过程回溯/复盘功能",
    "tengu_quiet_hollow":              "隐藏 interleaved thinking 摘要",
    # ── 对话压缩/上下文管理 ──
    "tengu_compact_cache_prefix":           "对话压缩时启用缓存前缀优化",
    "tengu_compact_line_prefix_killswitch": "关闭压缩行号前缀格式（killswitch）",
    "tengu_sm_compact_config":              "会话记忆压缩配置（token 数/消息阈值）",
    "tengu_sm_config":                      "会话记忆（Session Memory）通用配置",
    "tengu_slate_heron":                    "空闲后微压缩实验（间隔阈值/保留消息数）",
    "tengu_hawthorn_window":                "工具结果持久化滑动窗口大小（字符数）",
    "tengu_pebble_leaf_prune":              "对话树中修剪无子节点的叶子消息",
    "tengu_hawthorn_steeple":               "工具结果替换/持久化追踪开关",
    # ── 会话记忆 (Willow/Memory) ──
    "tengu_session_memory":            "会话记忆功能，自动提取和加载会话级上下文",
    "tengu_willow_mode":               "空闲检测模式，长时间无操作后提示是否继续",
    "tengu_willow_census_ttl_hours":   "记忆普查 TTL（小时）",
    "tengu_willow_refresh_ttl_hours":  "记忆刷新 TTL（小时）",
    "tengu_willow_sentinel_ttl_hours": "记忆哨兵 TTL（小时）",
    "tengu_plank_river_frost":         "意图分类实验（user_intent vs stated_intent）",
    "tengu_onyx_plover":               "自动记忆（Auto Memory）开关及触发条件",
    "tengu_bramble_lintel":            "自动记忆提取触发频率（每 N 条消息一次）",
    "tengu_coral_fern":                "系统提示中添加搜索过去上下文的记忆指引",
    "tengu_herring_clock":             "团队记忆目录（team/ 子目录共享记忆）",
    "tengu_moth_copse":                "过滤会话记忆中 AutoMem/TeamMem 类型",
    # ── 工具系统 ──
    "tengu_tool_pear":                      "启用特定 Anthropic API beta 功能",
    "tengu_tool_result_persistence":        "工具结果持久化存储",
    "tengu_tool_search_unsupported_models": "Tool Search 不支持的模型黑名单",
    "tengu_mcp_tool_search":                "MCP 工具搜索功能",
    "tengu_mcp_elicitation":                "MCP 服务器向用户请求额外信息（elicitation）",
    "tengu_brief_tool_enabled":             "简洁工具输出模式",
    "tengu_file_write_optimization":        "文件写入优化",
    "tengu_code_diff_cli":                  "CLI 中的代码 diff 显示",
    "tengu_pewter_kestrel":                 "各工具输出最大字符数限制",
    "tengu_summarize_tool_results":         "工具结果自动摘要",
    "tengu_read_dedup_killswitch":          "关闭文件读取去重优化（killswitch）",
    "tengu_glacier_2xr":                    "延迟工具列表展示格式控制",
    "tengu_defer_all_bn4":                  "强制所有非核心工具延迟加载",
    "tengu_defer_caveat_m9k":               "系统提示中添加延迟工具使用注意事项",
    "tengu_borax_j4w":                      "阻止特定内置工具被延迟加载",
    "tengu_tst_hint_m7r":                   "工具搜索列表中显示搜索提示",
    "tengu_satin_quoll":                    "工具结果大小限制配置",
    "tengu_sage_compass":                   "Advisor Tool（顾问工具）功能开关",
    "tengu_plum_vx3":                       "Web Search 用 Haiku 模型并禁用 thinking",
    # ── 流式输出/显示风格 ──
    "tengu_streaming_text":              "流式文本输出",
    "tengu_streaming_tool_execution2":   "流式工具执行显示（实时展示执行过程）",
    "tengu_swann_brevity":               "输出简洁度控制（focused = 精简输出）",
    "tengu_sotto_voce":                  "静默输出模式，减少冗余信息",
    "tengu_vinteuil_phrase":             "输出格式控制（Proust 命名系列）",
    "tengu_swinburne_dune":              "输出风格控制（Proust 命名系列）",
    "tengu_tern_alloy":                  "子代理扇出（subagent fanout）建议文案",
    "tengu_tide_elm":                    "/effort high 使用提示文案 A/B 测试",
    # ── 安全/权限 ──
    "tengu_destructive_command_warning":     "破坏性命令（rm -rf 等）显示警告",
    "tengu_disable_bypass_permissions_mode": "禁用 YOLO 模式（绕过权限检查）",
    "tengu_passport_quail":                  "非交互模式记忆/身份验证行为控制",
    "tengu_react_vulnerability_warning":     "React 依赖漏洞警告",
    "tengu_cork_m4q":                        "权限检查系统提示优化",
    "tengu_permission_explainer":            "权限请求时生成 AI 风险解释说明",
    "tengu_slate_thimble":                   "非交互模式下也允许启用特定功能",
    # ── 提示缓存 ──
    "tengu_cache_plum_violet":          "提示缓存优化",
    "tengu_prompt_cache_1h_config":     "1h TTL 提示缓存白名单配置",
    "tengu_system_prompt_global_cache": "系统提示词全局缓存（跨会话共享）",
    "tengu_kv7_prompt_sort":            "提示排序优化实验",
    # ── UI/UX/推广 ──
    "tengu_accept_with_feedback":          "接受权限时附带反馈",
    "tengu_birthday_hat":                  "生日彩蛋/装饰",
    "tengu_desktop_upsell":                "桌面客户端推广弹窗",
    "tengu_grey_step":                     "Effort 级别配置（旧版）",
    "tengu_grey_step2":                    "Effort 级别推荐配置（medium/high/ultrathink）",
    "tengu_penguin_mode_promo":            "Fast Mode 促销活动配置",
    "tengu_penguins_enabled":              "Fast Mode（快速模式）总开关",
    "tengu_prompt_suggestion":             "输入框空闲时显示提示建议",
    "tengu_chomp_inflection":              "Prompt Suggestion 的 GrowthBook 开关",
    "tengu_year_end_2025_campaign_promo":  "2025 年末营销活动推广",
    "tengu_jade_anvil_4":                  "用量超额（overage）UI 提示",
    "tengu_keybinding_customization_release": "自定义快捷键正式发布",
    "tengu_lodestone_enabled":             "自动注册 claude-cli:// 深度链接协议",
    "tengu_marble_sandcastle":             "非原生安装时禁用 Fast Mode",
    "tengu_c4w_usage_limit_notifications_enabled": "Claude for Work 用量限制通知",
    # ── 用户反馈/调查 ──
    "tengu_bad_survey_transcript_ask_config":      "差评后询问分享对话记录",
    "tengu_good_survey_transcript_ask_config":     "好评后询问分享对话记录",
    "tengu_negative_interaction_transcript_ask_config": "负面交互后询问分享对话记录",
    "tengu_feedback_survey_config":                "反馈调查弹窗频率和时机",
    "tengu_post_compact_survey":                   "压缩后显示满意度调查",
    # ── 定时任务 (Kairos) ──
    "tengu_kairos_cron":          "定时任务（Cron/Schedule）总开关",
    "tengu_kairos_cron_durable":  "持久化定时任务（跨会话保留）",
    "tengu_surreal_dali":         "Remote Trigger（远程触发器/定时代理）",
    # ── 版本/更新/安装 ──
    "tengu_version_config":              "最低版本检查，低于 minVersion 时提示更新",
    "tengu_max_version_config":          "最高版本限制",
    "tengu_pid_based_version_locking":   "基于 PID 的版本锁定，防多实例更新冲突",
    "tengu_native_installation":         "原生安装方式检测/配置",
    # ── Git/Worktree/PR ──
    "tengu_worktree_mode":   "Git Worktree 隔离模式",
    "tengu_pr_status_cli":   "CLI 中 PR 状态查看",
    # ── VS Code 扩展 ──
    "tengu_vscode_onboarding":    "VS Code 扩展新手引导",
    "tengu_vscode_review_upsell": "VS Code 代码审查推广",
    "tengu_vscode_cc_auth":       "VS Code 使用 Claude Code 认证",
    "tengu_quiet_fern":           "VS Code 实验门控标志",
    # ── MCP/外部集成 ──
    "tengu_basalt_3kr":               "MCP 服务器指令增量更新",
    "tengu_claudeai_mcp_connectors":  "Claude.ai MCP 连接器集成",
    "tengu_cobalt_frost":             "语音流 Deepgram Nova 3 语音识别引擎",
    "tengu_cobalt_lantern":           "GitHub Token 同步功能",
    "tengu_collage_kaleidoscope":     "剪贴板/截图图片拼贴",
    # ── 其他已知功能 ──
    "tengu_chair_sermon":         "消息内容规范化（附件映射/文本块合并）",
    "tengu_review_bughunter_config": "Ultra Review / Bug Hunter 代码审查配置",
    "tengu_scratch":              "Scratchpad 临时工作目录",
    "tengu_snippet_save":         "代码片段保存功能",
    "tengu_miraculo_the_bard":    "启动时后台预取任务开关",
    "tengu_malort_pedway":        "编排/协调模式子功能配置",
    "tengu_pewter_ledger":        "Plan Mode 中工具结果处理策略",
    "tengu_grey_wool":            "[Desktop] 桌面端 UI 相关功能",
    # ── 仅服务端/Desktop 端使用（CLI 中未引用） ──
    "tengu_birch_mist":              "[Desktop] 桌面端功能开关（强制开启）",
    "tengu_marble_anvil":            "[Desktop] 桌面端功能开关（强制开启）",
    "tengu_slate_nexus":             "[Desktop] 桌面端功能开关（强制开启）",
    "tengu_sepia_heron":             "[Desktop] 桌面端功能开关（强制关闭）",
    "tengu_sumi":                    "[Desktop] 桌面端功能开关（强制关闭）",
    "tengu_marble_whisper":          "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_marble_whisper2":         "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_oboe":                    "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_cobalt_compass":          "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_slate_ridge":             "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_tangerine_ladder_boost":  "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_workout2":                "[Desktop] 桌面端功能开关（默认开启）",
    "tengu_olive_hinge":             "[Desktop] 桌面端字符串配置（默认空）",
    "tengu_blue_coaster":            "[Desktop/预留] 未启用的功能开关",
    "tengu_brass_pebble":            "[Desktop/预留] 未启用的功能开关",
    "tengu_cobalt_raccoon":          "[Desktop/预留] 未启用的功能开关",
    "tengu_copper_lantern":          "[Desktop/预留] 未启用的功能开关",
    "tengu_copper_wren":             "[Desktop/预留] 未启用的功能开关",
    "tengu_coral_whistle":           "[Desktop/预留] 未启用的功能开关",
    "tengu_cork_lantern":            "[Desktop/预留] 未启用的功能开关",
    "tengu_dunwich_bell":            "[Desktop/预留] 未启用的功能开关",
    "tengu_flint_harbor":            "[Desktop/预留] 未启用的功能开关",
    "tengu_frozen_nest":             "[Desktop/预留] 未启用的功能开关",
    "tengu_hayate":                  "[Desktop/预留] 未启用的功能开关",
    "tengu_marble_fox":              "[Desktop/预留] 未启用的功能开关",
    "tengu_mulberry_fog":            "[Desktop/预留] 未启用的功能开关",
    "tengu_orchid_trellis":          "[Desktop/预留] 未启用的功能开关",
    "tengu_otk_slot_v1":             "[Desktop/预留] 未启用的功能开关",
    "tengu_red_coaster":             "[Desktop/预留] 未启用的功能开关",
    "tengu_scarf_coffee":            "[Desktop/预留] 未启用的功能开关",
    "tengu_silver_lantern":          "[Desktop/预留] 未启用的功能开关",
    "tengu_turnip_cathedral":        "[Desktop/预留] 未启用的功能开关",
    "tengu_walrus_canteen":          "[Desktop/预留] 未启用的功能开关",
    "tengu_bergotte_lantern":        "[Desktop/预留] 未启用的功能开关",
}

# 功能分类
FLAG_CATEGORIES = {
    "总开关/元信息":       ["auto_migrate_to_native", "ccr_auto_permission_mode", "tengu-off-switch", "tengu-top-of-feed-tip"],
    "遥测/事件上报":       ["tengu_1p_event_batch_config", "tengu_event_sampling_config", "tengu_log_datadog_events", "tengu_trace_lantern", "tengu_ant_attribution_header_new", "tengu_attribution_header", "tengu_frond_boric"],
    "插件/Agent Teams":    ["tengu_amber_flint", "tengu_amber_lattice", "tengu_amber_prism", "tengu_amber_quartz", "tengu_amber_stoat", "tengu_amber_wren"],
    "插件市场 (Harbor)":   ["tengu_harbor", "tengu_harbor_ledger", "tengu_harbor_permissions", "tengu_lapis_finch", "tengu_plugin_official_mkt_git_fallback", "tengu_gha_plugin_code_review"],
    "Bridge/桌面端通信":   ["tengu_bridge_min_version", "tengu_bridge_poll_interval_config", "tengu_bridge_poll_interval_ms", "tengu_bridge_repl_v2", "tengu_bridge_repl_v2_config", "tengu_copper_bridge"],
    "远程控制 (CCR)":      ["tengu_ccr_bridge", "tengu_ccr_bridge_multi_session", "tengu_ccr_bundle_max_bytes", "tengu_ccr_bundle_seed_enabled", "tengu_quartz_lantern"],
    "模型/推理":           ["tengu_opus_default_pro_plan", "tengu_immediate_model_command", "tengu_auto_mode_config", "tengu_crystal_beam", "tengu_turtle_carbon", "tengu_thinkback", "tengu_quiet_hollow"],
    "对话压缩/上下文":     ["tengu_compact_cache_prefix", "tengu_compact_line_prefix_killswitch", "tengu_sm_compact_config", "tengu_sm_config", "tengu_slate_heron", "tengu_hawthorn_window", "tengu_pebble_leaf_prune", "tengu_hawthorn_steeple"],
    "会话记忆 (Willow)":   ["tengu_session_memory", "tengu_willow_mode", "tengu_willow_census_ttl_hours", "tengu_willow_refresh_ttl_hours", "tengu_willow_sentinel_ttl_hours", "tengu_plank_river_frost", "tengu_onyx_plover", "tengu_bramble_lintel", "tengu_coral_fern", "tengu_herring_clock", "tengu_moth_copse"],
    "工具系统":            ["tengu_tool_pear", "tengu_tool_result_persistence", "tengu_tool_search_unsupported_models", "tengu_mcp_tool_search", "tengu_mcp_elicitation", "tengu_brief_tool_enabled", "tengu_file_write_optimization", "tengu_code_diff_cli", "tengu_pewter_kestrel", "tengu_summarize_tool_results", "tengu_read_dedup_killswitch", "tengu_glacier_2xr", "tengu_defer_all_bn4", "tengu_defer_caveat_m9k", "tengu_borax_j4w", "tengu_tst_hint_m7r", "tengu_satin_quoll", "tengu_sage_compass", "tengu_plum_vx3"],
    "输出/显示风格":       ["tengu_streaming_text", "tengu_streaming_tool_execution2", "tengu_swann_brevity", "tengu_sotto_voce", "tengu_vinteuil_phrase", "tengu_swinburne_dune", "tengu_tern_alloy", "tengu_tide_elm"],
    "安全/权限":           ["tengu_destructive_command_warning", "tengu_disable_bypass_permissions_mode", "tengu_passport_quail", "tengu_react_vulnerability_warning", "tengu_cork_m4q", "tengu_permission_explainer", "tengu_slate_thimble"],
    "提示缓存":            ["tengu_cache_plum_violet", "tengu_prompt_cache_1h_config", "tengu_system_prompt_global_cache", "tengu_kv7_prompt_sort"],
    "用户反馈/调查":       ["tengu_bad_survey_transcript_ask_config", "tengu_good_survey_transcript_ask_config", "tengu_negative_interaction_transcript_ask_config", "tengu_feedback_survey_config", "tengu_post_compact_survey"],
    "UI/UX/推广":          ["tengu_accept_with_feedback", "tengu_birthday_hat", "tengu_desktop_upsell", "tengu_grey_step", "tengu_grey_step2", "tengu_penguin_mode_promo", "tengu_penguins_enabled", "tengu_prompt_suggestion", "tengu_chomp_inflection", "tengu_year_end_2025_campaign_promo", "tengu_jade_anvil_4", "tengu_keybinding_customization_release", "tengu_lodestone_enabled", "tengu_marble_sandcastle", "tengu_c4w_usage_limit_notifications_enabled"],
    "定时任务 (Kairos)":   ["tengu_kairos_cron", "tengu_kairos_cron_durable", "tengu_surreal_dali"],
    "版本/更新/安装":      ["tengu_version_config", "tengu_max_version_config", "tengu_pid_based_version_locking", "tengu_native_installation"],
    "Git/PR":              ["tengu_worktree_mode", "tengu_pr_status_cli"],
    "VS Code 扩展":        ["tengu_vscode_onboarding", "tengu_vscode_review_upsell", "tengu_vscode_cc_auth", "tengu_quiet_fern"],
    "MCP/外部集成":        ["tengu_basalt_3kr", "tengu_claudeai_mcp_connectors", "tengu_cobalt_frost", "tengu_cobalt_lantern", "tengu_collage_kaleidoscope"],
    "其他功能":            ["tengu_chair_sermon", "tengu_review_bughunter_config", "tengu_scratch", "tengu_snippet_save", "tengu_miraculo_the_bard", "tengu_malort_pedway", "tengu_pewter_ledger", "tengu_grey_wool"],
    "仅 Desktop/预留":     ["tengu_birch_mist", "tengu_marble_anvil", "tengu_slate_nexus", "tengu_sepia_heron", "tengu_sumi", "tengu_marble_whisper", "tengu_marble_whisper2", "tengu_oboe", "tengu_cobalt_compass", "tengu_slate_ridge", "tengu_tangerine_ladder_boost", "tengu_workout2", "tengu_olive_hinge", "tengu_blue_coaster", "tengu_brass_pebble", "tengu_cobalt_raccoon", "tengu_copper_lantern", "tengu_copper_wren", "tengu_coral_whistle", "tengu_cork_lantern", "tengu_dunwich_bell", "tengu_flint_harbor", "tengu_frozen_nest", "tengu_hayate", "tengu_marble_fox", "tengu_mulberry_fog", "tengu_orchid_trellis", "tengu_otk_slot_v1", "tengu_red_coaster", "tengu_scarf_coffee", "tengu_silver_lantern", "tengu_turnip_cathedral", "tengu_walrus_canteen", "tengu_bergotte_lantern"],
}

# Build reverse lookup: flag_name -> category
_FLAG_TO_CATEGORY = {}
for cat, flags in FLAG_CATEGORIES.items():
    for f in flags:
        _FLAG_TO_CATEGORY[f] = cat


def find_config_file():
    """Find Claude Code's config file (~/.claude.json or ~/.claude/.config.json)."""
    home = Path.home()
    claude_dir = home / ".claude"

    # Check ~/.claude/.config.json first (newer versions)
    candidate = claude_dir / ".config.json"
    if candidate.exists():
        return candidate

    # Fall back to ~/.claude.json
    candidate = home / ".claude.json"
    if candidate.exists():
        return candidate

    # Check CLAUDE_CONFIG_DIR env
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        candidate = Path(config_dir) / ".claude.json"
        if candidate.exists():
            return candidate

    return None


def load_config(config_path):
    """Load and parse the Claude config JSON."""
    with open(config_path, "r") as f:
        return json.load(f)


def get_oauth_token_macos():
    """Extract OAuth token from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            creds = json.loads(result.stdout.strip())
            oauth = creds.get("claudeAiOauth", {})
            return oauth.get("accessToken")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None


def get_oauth_token_linux():
    """Extract OAuth token from Linux keyring via secret-tool."""
    try:
        result = subprocess.run(
            ["secret-tool", "lookup", "service", "Claude Code-credentials"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            creds = json.loads(result.stdout.strip())
            oauth = creds.get("claudeAiOauth", {})
            return oauth.get("accessToken")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None


def get_oauth_token():
    """Get OAuth token from system credential store."""
    system = platform.system()
    if system == "Darwin":
        return get_oauth_token_macos()
    elif system == "Linux":
        return get_oauth_token_linux()
    return None


def build_attributes(config):
    """Build GrowthBook attributes from config."""
    oauth_account = config.get("oauthAccount", {})

    attrs = {
        "id": config.get("userID", ""),
        "sessionId": "feature-dump-session",
        "deviceID": config.get("userID", ""),
        "platform": sys.platform,
    }

    # Optional fields from oauthAccount
    org_uuid = oauth_account.get("organizationUuid")
    if org_uuid:
        attrs["organizationUUID"] = org_uuid

    account_uuid = oauth_account.get("accountUuid")
    if account_uuid:
        attrs["accountUUID"] = account_uuid

    email = oauth_account.get("emailAddress")
    if email:
        attrs["email"] = email

    attrs["userType"] = "external"
    attrs["apiBaseUrlHost"] = "api.anthropic.com"

    # These come from the OAuth credential, try config cache
    sub_type = oauth_account.get("subscriptionType") or config.get("subscriptionType")
    if sub_type:
        attrs["subscriptionType"] = sub_type

    return attrs


def fetch_features(attributes, oauth_token=None):
    """Send remote eval request to GrowthBook endpoint."""
    url = f"{GROWTHBOOK_API_HOST}/api/eval/{GROWTHBOOK_CLIENT_KEY}"

    payload = {
        "attributes": attributes,
        "forcedVariations": {},
        "forcedFeatures": [],
        "url": ""
    }

    headers = {"Content-Type": "application/json"}
    if oauth_token:
        headers["Authorization"] = f"Bearer {oauth_token}"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[!] HTTP {e.code}: {body}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[!] Request failed: {e.reason}", file=sys.stderr)
        return None


def truncate(s, maxlen):
    """Truncate string with ellipsis."""
    return s if len(s) <= maxlen else s[:maxlen - 3] + "..."


def calc_display_width(s):
    """Calculate display width considering CJK characters as width 2."""
    w = 0
    for ch in s:
        w += 2 if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u30ff' or '\uff00' <= ch <= '\uffef' else 1
    return w


def pad_to_width(s, width):
    """Pad string to target display width."""
    current = calc_display_width(s)
    return s + " " * max(0, width - current)


def print_table(rows, col_widths):
    """Print a formatted table with proper alignment."""
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    print(sep)
    for i, row in enumerate(rows):
        cells = []
        for j, (cell, w) in enumerate(zip(row, col_widths)):
            cells.append(" " + pad_to_width(truncate(cell, w), w) + " ")
        print("|" + "|".join(cells) + "|")
        if i == 0:
            print(sep)
    print(sep)


def print_features(response, mode="pretty"):
    """Display feature flags."""
    features = response.get("features", {})

    if mode == "json":
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return

    print(f"\n  Claude Code Feature Flags — {len(features)} total\n")

    # === A/B Experiments (always show first) ===
    experiments = [(n, i) for n, i in features.items()
                   if (i.get("experimentResult") or {}).get("inExperiment")]
    if experiments:
        print(f"\n  ▸ A/B 实验（{len(experiments)} 个）\n")
        rows = [("标志名", "实验名", "你的分组", "所有分组", "分桶依据", "说明")]
        for name, info in sorted(experiments):
            desc = FLAG_DESCRIPTIONS.get(name, "")
            exp_result = info.get("experimentResult", {})
            exp_info = info.get("experiment", {})
            val = json.dumps(info.get("value"), ensure_ascii=False)
            variations = json.dumps(exp_info.get("variations", []), ensure_ascii=False)
            rows.append((
                name,
                exp_info.get("key", "?"),
                f"#{exp_result.get('variationId', '?')} → {val}",
                variations,
                exp_info.get("hashAttribute", "?"),
                desc,
            ))
        print_table(rows, [30, 45, 28, 50, 14, 40])

    if mode == "experiments":
        return

    # === Group by category ===
    exp_names = {n for n, _ in experiments}
    categorized = {}
    uncategorized = []

    for name, info in features.items():
        if name in exp_names:
            continue
        cat = _FLAG_TO_CATEGORY.get(name)
        if cat:
            categorized.setdefault(cat, []).append((name, info))
        else:
            uncategorized.append((name, info))

    # Print each category in the order defined in FLAG_CATEGORIES
    for cat in FLAG_CATEGORIES:
        items = categorized.get(cat, [])
        if not items:
            continue
        print(f"\n  ▸ {cat}（{len(items)} 个）\n")
        rows = [("状态", "标志名", "值", "说明")]
        for name, info in sorted(items):
            desc = FLAG_DESCRIPTIONS.get(name, "")
            val = json.dumps(info.get("value"), ensure_ascii=False)
            src = info.get("source", "")
            status = "ON" if info.get("on") else "OFF"
            if src == "force":
                status += " !"
            rows.append((status, name, val, desc))
        print_table(rows, [5, 50, 50, 48])

    # Print uncategorized if any
    if uncategorized:
        print(f"\n  ▸ 未分类（{len(uncategorized)} 个）\n")
        rows = [("状态", "标志名", "值", "说明")]
        for name, info in sorted(uncategorized):
            desc = FLAG_DESCRIPTIONS.get(name, "")
            val = json.dumps(info.get("value"), ensure_ascii=False)
            status = "ON" if info.get("on") else "OFF"
            rows.append((status, name, val, desc))
        print_table(rows, [5, 50, 50, 48])


def main():
    mode = "pretty"
    if "--json" in sys.argv:
        mode = "json"
    elif "--experiments" in sys.argv:
        mode = "experiments"

    # Step 1: Find config
    config_path = find_config_file()
    if not config_path:
        print("[!] Claude Code config not found. Is Claude Code installed?", file=sys.stderr)
        sys.exit(1)

    if mode != "json":
        print(f"[*] Config: {config_path}")

    config = load_config(config_path)
    user_id = config.get("userID", "(unknown)")
    if mode != "json":
        print(f"[*] Device ID: {user_id[:16]}...")

    # Step 2: Get OAuth token
    oauth_token = get_oauth_token()
    if mode != "json":
        if oauth_token:
            print(f"[*] OAuth token: {oauth_token[:20]}...{oauth_token[-10:]}")
        else:
            print("[!] No OAuth token found — request may fail or return limited results")

    # Step 3: Build attributes
    attributes = build_attributes(config)
    if mode != "json":
        print(f"[*] Attributes: {json.dumps({k: v for k, v in attributes.items() if k != 'email'}, ensure_ascii=False)}")

    # Step 4: Fetch features
    if mode != "json":
        print(f"[*] Requesting: POST {GROWTHBOOK_API_HOST}/api/eval/{GROWTHBOOK_CLIENT_KEY}")

    response = fetch_features(attributes, oauth_token)
    if not response:
        # Fallback: show cached features from config
        cached = config.get("cachedGrowthBookFeatures", {})
        if cached:
            print(f"\n[!] API request failed. Showing {len(cached)} cached features from local config:\n",
                  file=sys.stderr)
            for k, v in sorted(cached.items()):
                val_str = json.dumps(v, ensure_ascii=False)
                if len(val_str) > 80:
                    val_str = val_str[:77] + "..."
                print(f"  {k}: {val_str}")
        sys.exit(1)

    # Step 5: Display
    print_features(response, mode)


if __name__ == "__main__":
    main()
