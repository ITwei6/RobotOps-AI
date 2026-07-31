import unittest
from unittest.mock import patch

from agent_service.app.llm.deepseek import generate_structured_report
from agent_service.app.models import DiagnosisReport


class FakeStructuredDeepSeek:
    last_method = None
    last_prompt = ""

    def __init__(self, model, temperature, max_retries):
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    def with_structured_output(self, schema, *, method):
        self.schema = schema
        FakeStructuredDeepSeek.last_method = method
        return self

    def invoke(self, prompt):
        self.prompt = prompt
        FakeStructuredDeepSeek.last_prompt = prompt
        return DiagnosisReport(
            summary="DeepSeek 结构化报告",
            suspected_module="interaction",
            possible_causes=["触摸任务被 interaction 前置检查拦截。"],
            evidence_logs=[
                {
                    "module_name": "interaction",
                    "file_name": "interaction.log",
                    "line_no": 3,
                    "message": "ignore touch trigger",
                }
            ],
            evidence_sources=[],
            recommended_actions=["联动 mc.log 确认当前 action_id。"],
            confidence=0.8,
            questions_for_human=[],
            agent_version="llm-test",
        )


class DeepSeekWrapperTest(unittest.TestCase):
    def test_generate_structured_report_uses_langchain_deepseek_schema(self):
        with patch("agent_service.app.llm.deepseek.ChatDeepSeek", FakeStructuredDeepSeek):
            report = generate_structured_report(
                model="deepseek-v4-flash",
                request={
                    "bug": {
                        "title": "触摸无反应",
                        "robot_type": "ROBOT_TYPE_T",
                        "main_module": "interaction",
                        "occurred_time": 1785396730000,
                    },
                    "logs": [
                        {
                            "module_name": "interaction",
                            "message": "ignore touch trigger",
                            "raw_line": "WARN ignore touch trigger",
                        }
                    ],
                },
                rule_report={
                    "summary": "规则 baseline",
                    "suspected_module": "interaction",
                    "possible_causes": ["规则原因"],
                    "evidence_logs": [],
                    "evidence_sources": [],
                    "recommended_actions": ["规则建议"],
                    "confidence": 0.8,
                    "questions_for_human": [],
                },
            )

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertEqual(report["evidence_logs"][0]["line_no"], 3)
        self.assertEqual(FakeStructuredDeepSeek.last_method, "json_mode")
        self.assertIn("DiagnosisReport JSON schema", FakeStructuredDeepSeek.last_prompt)
        self.assertIn('"evidence_logs"', FakeStructuredDeepSeek.last_prompt)


if __name__ == "__main__":
    unittest.main()
