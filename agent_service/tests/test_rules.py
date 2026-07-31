import unittest

from agent_service.app.rules import diagnose


class DiagnoseRulesTest(unittest.TestCase):
    def test_touch_action_blocked_report(self):
        report = diagnose(
            {
                "bug": {
                    "bug_id": "bug-000001",
                    "title": "触摸后机器人没有反应",
                    "description": "T 型机器人拍触摸板没反应",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "occurred_time": 1785396730000,
                    "source_repo": "/home/dev/workspace/interaction",
                    "branch": "main",
                },
                "logs": [
                    {
                        "module_name": "interaction",
                        "file_name": "interaction.log",
                        "line_no": 3,
                        "log_time": 1785396730150,
                        "log_level": "warn",
                        "message": "Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger, action_id: 100",
                        "raw_line": "2026-07-30 15:32:10.150 WARN Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger, action_id: 100",
                    }
                ],
            }
        )

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertGreaterEqual(report["confidence"], 0.8)
        self.assertEqual(report["evidence_logs"][0]["line_no"], 3)
        self.assertEqual(
            report["execution_chain"],
            [
                "触摸事件进入 interaction",
                "T1 CheckTouch 前置检查拦截",
                "未进入触摸任务创建/派发阶段",
            ],
        )
        self.assertEqual(report["evidence_sources"], [])
        self.assertTrue(any("T1Checker::CheckTouch" in question for question in report["questions_for_human"]))

    def test_low_confidence_without_evidence(self):
        report = diagnose(
            {
                "bug": {
                    "title": "机器人没有反应",
                    "description": "没有日志",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "occurred_time": 1785396730000,
                },
                "logs": [],
            }
        )

        self.assertLess(report["confidence"], 0.3)
        self.assertTrue(report["questions_for_human"])


if __name__ == "__main__":
    unittest.main()
