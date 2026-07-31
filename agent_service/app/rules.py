from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence


INTERACTION_SOURCE_HINTS = {
    "check_touch": {
        "file_path": "interaction/src/scheduler/checker/t1_checker.cpp",
        "function_name": "T1Checker::CheckTouch",
        "matched_text": "Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT",
    },
    "play_move": {
        "file_path": "interaction/src/scheduler/plugin/service/play_move_service_plugin.cpp",
        "function_name": "PlayMoveServicePlugin::HandlePlayMove",
        "matched_text": "Self check not passed, skip DispatchMove",
    },
    "worker_manager": {
        "file_path": "interaction/src/worker/worker_manager.cpp",
        "function_name": "WorkerManager::ExecTask",
        "matched_text": "blocked by rule / rejected by running task",
    },
    "action_skill": {
        "file_path": "interaction/src/skill/atomic/action_skill.cpp",
        "function_name": "ActionSkill::Exec",
        "matched_text": "SetMcAction",
    },
    "move_skill": {
        "file_path": "interaction/src/skill/atomic/move_skill.cpp",
        "function_name": "MoveSkill::Exec",
        "matched_text": "/aima/mc/locomotion/velocity",
    },
}


@dataclass(frozen=True)
class RuleMatch:
    name: str
    suspected_module: str
    summary: str
    cause: str
    action: str
    source_hint_key: str = ""
    confidence: float = 0.55


RULES: Sequence[RuleMatch] = (
    RuleMatch(
        name="touch_action_blocked",
        suspected_module="interaction",
        summary="触摸事件到达 interaction，但被 T1 CheckTouch 根据当前 MC action 拦截。",
        cause="当前 MC action 处于 DAMPING_DEFAULT 或 PASSIVE_DEFAULT，interaction 按安全规则不创建触摸任务。",
        action="确认触摸发生时 MC action_id 是否符合预期，并联动 mc.log 判断底层是否处于急停、阻尼或未站立状态。",
        source_hint_key="check_touch",
        confidence=0.82,
    ),
    RuleMatch(
        name="self_check_not_passed",
        suspected_module="interaction",
        summary="interaction 收到请求后因 self check 未通过而跳过任务派发。",
        cause="机器人自检状态未达到可执行任务状态，Scheduler/Plugin 层拦截了请求。",
        action="检查 self_check_state、启动自检日志、hds.log 和 sm.log，确认是否处于开箱、自检或故障态。",
        source_hint_key="play_move",
        confidence=0.76,
    ),
    RuleMatch(
        name="low_battery_or_charging",
        suspected_module="bms",
        summary="请求被低电量或充电状态限制。",
        cause="interaction 的 Checker 根据 bms/pmu 状态拒绝移动、触摸、跟随或编排任务。",
        action="检查 bms 日志中的电量等级、is_charging 状态和 robot_config 是否允许忽略低电限制。",
        confidence=0.7,
    ),
    RuleMatch(
        name="task_factory_failed",
        suspected_module="interaction",
        summary="interaction 通过前置检查后，任务创建失败。",
        cause="TaskFactory 未能获取对应机型的 TaskDescription，或 TaskDescription 未生成有效 SkillParamList。",
        action="根据机器人类型检查 T1/Q1 TaskDescription 注册和请求参数是否合法。",
        confidence=0.68,
    ),
    RuleMatch(
        name="worker_rejected",
        suspected_module="interaction",
        summary="任务已创建，但 WorkerManager 仲裁阶段拒绝执行。",
        cause="已有运行任务、同类型任务、规则优先级或资源优先级导致新任务被拒绝。",
        action="查看 active_workers、running_task、arbitration decision 和 action_manager.yaml 对应规则。",
        source_hint_key="worker_manager",
        confidence=0.72,
    ),
    RuleMatch(
        name="action_skill_failed",
        suspected_module="mc",
        summary="ActionSkill 调用 MC SetMcAction 失败或等待目标 action 超时。",
        cause="interaction 已尝试切换 MC action，但 MC RPC 返回失败或状态未切到目标 action。",
        action="联动 mc.log 查看 SetMcAction 返回码、当前 action_id 和 MC 状态机迁移是否允许。",
        source_hint_key="action_skill",
        confidence=0.78,
    ),
    RuleMatch(
        name="move_skill_odom_timeout",
        suspected_module="mc",
        summary="MoveSkill 发布速度后，里程计目标未按预期到达或超时。",
        cause="移动指令已由 interaction 下发，但 odom 数据不可用、运动状态不支持速度指令或 MC 未执行。",
        action="检查 /odom 是否新鲜、MoveSkill 目标距离/角度、mc.log 当前 action 是否为可移动态。",
        source_hint_key="move_skill",
        confidence=0.74,
    ),
)


RULE_KEYWORDS = {
    "touch_action_blocked": (
        "DAMPING_DEFAULT or PASSIVE_DEFAULT",
        "ignore touch trigger",
        "touch task not created because checker returned false",
    ),
    "self_check_not_passed": (
        "Self check not passed",
        "self_check_state",
        "skip DispatchMove",
        "skip touch",
    ),
    "low_battery_or_charging": (
        "Battery level is critically low",
        "电量状态过低",
        "is_charging",
        "low battery",
    ),
    "task_factory_failed": (
        "Failed to create task",
        "创建Move任务失败",
        "Failed to get task description",
        "Failed to get skill param list",
    ),
    "worker_rejected": (
        "blocked by rule",
        "rejected by running task",
        "same type task is running",
        "arbitration",
    ),
    "action_skill_failed": (
        "ActionSkill",
        "SetMcAction失败",
        "超时未能设置成功",
        "target_action_id",
    ),
    "move_skill_odom_timeout": (
        "MoveSkill",
        "里程计数据不可用",
        "超时",
        "pub发送MoveSkill消息",
    ),
}


def diagnose(payload: Dict[str, Any]) -> Dict[str, Any]:
    bug = payload.get("bug", {})
    logs = list(payload.get("logs", []))
    sources = list(payload.get("sources", []))

    matches = _match_rules(logs)
    selected_logs = _select_evidence_logs(logs, matches)
    selected_sources = _merge_source_evidence(sources, matches, bug)

    if not matches:
        return _low_confidence_report(bug, logs, sources)

    suspected_module = _choose_suspected_module(matches, bug)
    confidence = _calculate_confidence(matches, selected_logs, selected_sources)

    summary_parts = []
    possible_causes = []
    recommended_actions = []
    for match in matches:
        if match.summary not in summary_parts:
            summary_parts.append(match.summary)
        if match.cause not in possible_causes:
            possible_causes.append(match.cause)
        if match.action not in recommended_actions:
            recommended_actions.append(match.action)

    return {
        "summary": "；".join(summary_parts),
        "suspected_module": suspected_module,
        "possible_causes": possible_causes,
        "execution_chain": _execution_chain(matches),
        "evidence_logs": selected_logs,
        "evidence_sources": selected_sources,
        "recommended_actions": recommended_actions,
        "confidence": confidence,
        "questions_for_human": _questions_for(matches, bug, logs),
        "agent_version": "rule-template-v1",
        "status": "TASK_STATUS_SUCCEEDED",
    }


def _match_rules(logs: Sequence[Dict[str, Any]]) -> List[RuleMatch]:
    matched: List[RuleMatch] = []
    text = "\n".join(_log_text(log) for log in logs)
    for rule in RULES:
        keywords = RULE_KEYWORDS[rule.name]
        if any(keyword.lower() in text.lower() for keyword in keywords):
            matched.append(rule)
    return matched


def _select_evidence_logs(logs: Sequence[Dict[str, Any]], matches: Sequence[RuleMatch]) -> List[Dict[str, Any]]:
    if not logs:
        return []

    keywords = [keyword for match in matches for keyword in RULE_KEYWORDS[match.name]]
    selected = []
    for log in logs:
        text = _log_text(log).lower()
        if any(keyword.lower() in text for keyword in keywords):
            selected.append(_normalize_log(log))

    if selected:
        return selected[:20]

    warn_or_error = [
        _normalize_log(log)
        for log in logs
        if str(log.get("log_level", "")).lower() in {"warn", "warning", "error", "fatal"}
    ]
    return warn_or_error[:20]


def _merge_source_evidence(
    sources: Sequence[Dict[str, Any]],
    matches: Sequence[RuleMatch],
    bug: Dict[str, Any],
) -> List[Dict[str, Any]]:
    # Rule hints are navigation suggestions, not source evidence. Only a source
    # tool result with a real file path may enter evidence_sources.
    return [_normalize_source(source) for source in sources if source.get("file_path")][:20]


def _low_confidence_report(
    bug: Dict[str, Any],
    logs: Sequence[Dict[str, Any]],
    sources: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    selected_logs = _select_evidence_logs(logs, ())
    selected_sources = [_normalize_source(source) for source in sources if source.get("file_path")][:10]
    module = str(bug.get("main_module") or "unknown")
    return {
        "summary": "当前日志证据不足，未命中已知模块诊断规则，不能给出高置信度结论。",
        "suspected_module": module,
        "possible_causes": ["需要补充发生时间窗口内的 interaction、mc、hds、sm、agent 日志后再判断。"],
        "execution_chain": [],
        "evidence_logs": selected_logs,
        "evidence_sources": selected_sources,
        "recommended_actions": [
            "确认 Bug 发生时间是否准确。",
            "补充 occurred_time 前后 5 分钟多模块日志上下文。",
            "优先检查主模块及其关联模块日志中的请求入口、状态检查、任务创建、任务仲裁和底层调用关键日志。",
        ],
        "confidence": 0.25 if selected_logs or selected_sources else 0.15,
        "questions_for_human": [
            "飞书工单中的发生时间是否为机器人本地时间？",
            "日志包是否包含主模块及其关联模块的完整时间窗口日志？",
            "机器人类型是 T 型还是 Q 型，是否存在机型规则差异？",
        ],
        "agent_version": "rule-template-v1",
        "status": "TASK_STATUS_SUCCEEDED",
    }


def _choose_suspected_module(matches: Sequence[RuleMatch], bug: Dict[str, Any]) -> str:
    module_scores: Dict[str, float] = {}
    for match in matches:
        module_scores[match.suspected_module] = module_scores.get(match.suspected_module, 0.0) + match.confidence

    main_module = str(bug.get("main_module") or "")
    if main_module and main_module in module_scores:
        module_scores[main_module] += 0.1

    return max(module_scores.items(), key=lambda item: item[1])[0]


def _execution_chain(matches: Sequence[RuleMatch]) -> List[str]:
    """Describe only execution stages supported by matched evidence."""
    chain: List[str] = []
    names = {match.name for match in matches}
    if "touch_action_blocked" in names:
        chain.extend(
            [
                "触摸事件进入 interaction",
                "T1 CheckTouch 前置检查拦截",
                "未进入触摸任务创建/派发阶段",
            ]
        )
    if "self_check_not_passed" in names:
        chain.append("self check 未通过，任务派发被跳过")
    if "task_factory_failed" in names:
        chain.append("TaskFactory 任务创建失败")
    if "worker_rejected" in names:
        chain.append("WorkerManager 仲裁拒绝任务")
    if "action_skill_failed" in names:
        chain.append("ActionSkill 调用 MC action 失败或超时")
    if "move_skill_odom_timeout" in names:
        chain.append("MoveSkill 已发布移动请求但等待运动反馈超时")
    return list(dict.fromkeys(chain))


def _calculate_confidence(
    matches: Sequence[RuleMatch],
    logs: Sequence[Dict[str, Any]],
    sources: Sequence[Dict[str, Any]],
) -> float:
    if not matches:
        return 0.15
    base = max(match.confidence for match in matches)
    if len(matches) > 1:
        base += 0.05
    if logs:
        base += 0.05
    if sources:
        base += 0.05
    return round(min(base, 0.92), 2)


def _questions_for(matches: Sequence[RuleMatch], bug: Dict[str, Any], logs: Sequence[Dict[str, Any]]) -> List[str]:
    questions = []
    robot_type = str(bug.get("robot_type", ""))
    if robot_type not in {"ROBOT_TYPE_T", "ROBOT_TYPE_Q", "T", "Q", "T1", "Q1"}:
        questions.append("请确认机器人类型，T 型和 Q 型 interaction 规则不同。")
    if not logs:
        questions.append("请补充发生时间前后主模块及关联模块的日志。")
    if any(match.name in {"action_skill_failed", "move_skill_odom_timeout"} for match in matches):
        questions.append("请确认 mc.log 中当前 action_id 是否进入可移动态。")
    if any(match.name == "low_battery_or_charging" for match in matches):
        questions.append("请确认问题发生时机器人是否正在充电或处于低电量等级。")
    source_hints = [
        INTERACTION_SOURCE_HINTS[match.source_hint_key]["function_name"]
        for match in matches
        if match.source_hint_key in INTERACTION_SOURCE_HINTS
    ]
    if source_hints:
        questions.append("请通过源码检索确认以下位置：" + "、".join(dict.fromkeys(source_hints)) + "。")
    if not questions:
        questions.append("请开发工程师确认日志证据与源码位置是否匹配当前分支/commit。")
    return questions


def _log_text(log: Dict[str, Any]) -> str:
    return " ".join(
        str(log.get(key, ""))
        for key in ("module_name", "file_name", "log_level", "message", "raw_line")
    )


def _normalize_log(log: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "module_name": str(log.get("module_name", "")),
        "file_name": str(log.get("file_name", "")),
        "line_no": int(log.get("line_no") or 0),
        "log_time": int(log.get("log_time") or 0),
        "log_level": str(log.get("log_level", "")),
        "message": str(log.get("message", "")),
        "raw_line": str(log.get("raw_line", "")),
    }


def _normalize_source(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "repo": str(source.get("repo", "")),
        "branch": str(source.get("branch", "")),
        "commit": str(source.get("commit", "")),
        "file_path": str(source.get("file_path", "")),
        "function_name": str(source.get("function_name", "")),
        "matched_text": str(source.get("matched_text", "")),
        "snippet": str(source.get("snippet", "")),
    }


def _repo_name(source_repo: str) -> str:
    if not source_repo:
        return ""
    return source_repo.rstrip("/").split("/")[-1]
