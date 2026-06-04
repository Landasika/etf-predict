# Nightly Review Feishu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 23:00 MACD-optimization Feishu follow-up with a nightly review report covering parameter updates, today recap, and tomorrow focus.

**Architecture:** Keep daytime Feishu operation reports unchanged. Add a focused nightly report generator that consumes shared position rows and the scheduler optimization status. Wire MACD optimization completion to send the nightly report instead of reusing the operation-report sender.

**Tech Stack:** Python, FastAPI scheduler service, existing Feishu notifier, pytest.

---

### Task 1: Nightly Report Generator

**Files:**
- Create: `core/nightly_review_report.py`
- Test: `tests/test_nightly_review_report.py`

- [ ] **Step 1: Write failing tests**

```python
def test_nightly_review_report_includes_recap_operations_and_optimization(monkeypatch):
    from core import nightly_review_report

    monkeypatch.setattr(nightly_review_report, "build_feishu_operation_rows", lambda: {
        "success": True,
        "data_date": "20260604",
        "data": [
            {
                "code": "512690.SH",
                "name": "酒ETF",
                "pct_chg": -2.48,
                "daily_profit": -24.77,
                "previous_positions_used": 5,
                "positions_used": 0,
                "today_action_count": -5,
                "today_operation": "卖出5仓",
            },
            {
                "code": "563380.SH",
                "name": "航空航天ETF",
                "pct_chg": -0.39,
                "daily_profit": 0,
                "previous_positions_used": 0,
                "positions_used": 2,
                "today_action_count": 2,
                "today_operation": "买入2仓",
            },
        ],
    })

    report = nightly_review_report.generate_nightly_review_report({
        "last_result": "成功: 2/2",
        "completed_etfs": 2,
        "failed_etfs": 0,
        "total_etfs": 2,
        "changed_params": [
            {
                "code": "512690.SH",
                "name": "酒ETF",
                "old_params": {"macd_fast": 8, "macd_slow": 17, "macd_signal": 5},
                "new_params": {"macd_fast": 10, "macd_slow": 21, "macd_signal": 7},
                "return_pct": 12.3,
            }
        ],
    })

    assert "# 🌙 ETF 夜间复盘" in report
    assert "20260604" in report
    assert "今日总收益 | ¥-24.77" in report
    assert "卖出 | 1个 | 共5仓" in report
    assert "买入 | 1个 | 共2仓" in report
    assert "酒ETF | 8/17/5 -> 10/21/7" in report
    assert "明日重点关注" in report
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_nightly_review_report.py -q`

Expected: FAIL because `core.nightly_review_report` does not exist.

- [ ] **Step 3: Implement minimal generator**

Create `core/nightly_review_report.py` with `generate_nightly_review_report(optimization_status=None)`. It should read `build_feishu_operation_rows()`, calculate daily recap from `daily_profit`, summarize buy/sell/hold, render parameter changes from `optimization_status["changed_params"]`, and list tomorrow focus from non-zero `today_action_count`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_nightly_review_report.py -q`

Expected: PASS.

### Task 2: Scheduler Wiring

**Files:**
- Modify: `core/data_update_scheduler.py`
- Test: `tests/test_nightly_review_report.py`

- [ ] **Step 1: Write failing scheduler test**

```python
def test_macd_optimization_notify_feishu_sends_nightly_review(monkeypatch):
    from core.data_update_scheduler import DataUpdateScheduler

    scheduler = DataUpdateScheduler()
    scheduler.macd_optimization_notify_feishu = True
    scheduler.macd_optimization_status["completed_etfs"] = 1

    sent = {}
    monkeypatch.setattr(
        "core.nightly_review_report.generate_nightly_review_report",
        lambda status: sent.setdefault("status", status) or "nightly report",
    )

    class FakeNotifier:
        async def send_message(self, message, title=None):
            sent["message"] = message
            sent["title"] = title
            return True

    monkeypatch.setattr("core.feishu_notifier.get_feishu_notifier", lambda: FakeNotifier())

    scheduler._send_nightly_review_notification()

    assert sent["message"] == "nightly report"
    assert sent["title"] == "🌙 ETF夜间复盘"
    assert sent["status"] is scheduler.macd_optimization_status
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_nightly_review_report.py::test_macd_optimization_notify_feishu_sends_nightly_review -q`

Expected: FAIL because `_send_nightly_review_notification` does not exist.

- [ ] **Step 3: Implement scheduler method and wiring**

Add `_send_nightly_review_notification()` to `DataUpdateScheduler`. In `_run_macd_optimization()`, replace `self._send_feishu_notification()` with `self._send_nightly_review_notification()` when `macd_optimization_notify_feishu` is enabled.

- [ ] **Step 4: Run scheduler test**

Run: `pytest tests/test_nightly_review_report.py::test_macd_optimization_notify_feishu_sends_nightly_review -q`

Expected: PASS.

### Task 3: Optimization Status Detail

**Files:**
- Modify: `core/data_update_scheduler.py`
- Test: `tests/test_nightly_review_report.py`

- [ ] **Step 1: Write failing test for changed parameter capture**

Add a test around `_run_macd_optimization()` with fake watchlist, fake optimizer, and fake save function. Assert `macd_optimization_status["changed_params"]` contains code, name, old params, new params, and return pct.

- [ ] **Step 2: Implement changed parameter capture**

Initialize `changed_params` at the start of `_run_macd_optimization()`. Before replacing ETF parameters, store old params from `etf.get("optimized_macd_params")`; after optimization, append the change record.

- [ ] **Step 3: Run focused tests**

Run: `pytest tests/test_nightly_review_report.py tests/test_scheduler_settings_service.py -q`

Expected: PASS.

### Task 4: Verification And Deployment

**Files:**
- No new files beyond implementation and tests.

- [ ] **Step 1: Full test suite**

Run: `pytest -q`

Expected: `116+ passed` with existing warnings only.

- [ ] **Step 2: Commit and push**

```bash
git add core/nightly_review_report.py core/data_update_scheduler.py tests/test_nightly_review_report.py docs/superpowers/plans/2026-06-04-nightly-review-feishu.md
git commit -m "feat: send nightly review after parameter optimization"
git push origin main
```

- [ ] **Step 3: Remote deploy**

Sync `/root/etf-predict` to `origin/main`, preserve `data/`, `conf.json`, and remote `8000:8000` compose port, then run:

```bash
docker compose up -d --build --force-recreate etf-predict
```

- [ ] **Step 4: Remote verification**

Verify health, commit hash, and generate a dry-run nightly report inside the container:

```bash
docker exec -i etf-predict python - <<'PY'
from core.nightly_review_report import generate_nightly_review_report
print(generate_nightly_review_report({"last_result": "手动验证", "changed_params": []}).splitlines()[:30])
PY
```

Expected: report title is `# 🌙 ETF 夜间复盘` and includes today recap and tomorrow focus.
