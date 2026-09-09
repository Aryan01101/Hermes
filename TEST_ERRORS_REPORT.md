# Hermes Test Results - Error Report

**Date:** 2026-09-07
**Environment:** Local development with `.env` credentials

---

## ✅ Test Summary

| Test Suite | Total | Passed | Failed | Pass Rate |
|------------|-------|--------|--------|-----------|
| **Unit Tests** | 7 | 7 | 0 | **100%** ✅ |
| **Integration Tests** | 20 | 8 | 12 | 40% ⚠️ |
| **Overall** | 27 | 15 | 12 | 56% |

---

## 🎯 Unit Tests - All Passing

```bash
pytest tests/unit/ -v
```

**Result:** 7/7 tests passing ✅

All email service tests (reply extraction, header parsing, etc.) are working correctly.

---

## ⚠️ Integration Tests - Issues Found

### Test Results Breakdown

**Passing Tests (8/20):**
- ✅ `test_approval_flow_with_high_confidence`
- ✅ `test_approval_flow_logs_events`
- ✅ `test_unknown_reviewer_handling`
- ✅ `test_multiple_redraft_iterations`
- ✅ `test_redraft_incorporates_feedback`
- ✅ `test_redraft_version_number_increments`
- ✅ `test_rejection_prevents_email_send`
- ✅ `test_rejection_allows_new_thread`

**Failing Tests (12/20):**
- ❌ `test_complete_approval_flow`
- ❌ `test_trailing_email_in_existing_thread`
- ❌ `test_no_pending_drafts_scenario`
- ❌ `test_thread_detection_by_message_id`
- ❌ `test_unknown_whatsapp_action`
- ❌ `test_empty_email_body`
- ❌ `test_very_long_email_content`
- ❌ `test_multiple_references_in_header`
- ❌ `test_malformed_email_headers`
- ❌ `test_confidence_score_edge_cases`
- ❌ `test_complete_redraft_flow`
- ❌ `test_complete_rejection_flow`

---

## 🔴 Critical Issues

### Issue #1: PostgresSaver Context Manager Error

**Error:**
```
AttributeError: '_GeneratorContextManager' object has no attribute 'setup'
```

**Location:** `src/workflows/graph.py:422`

**Root Cause:**
```python
# Current (incorrect) code:
_checkpointer_instance = PostgresSaver.from_conn_string(
    settings.database_url
)
_checkpointer_instance.setup()  # ❌ Fails - this is a context manager, not an instance
```

**Issue:** `PostgresSaver.from_conn_string()` returns a context manager (generator), not a PostgresSaver instance. The code is trying to call `.setup()` on the context manager object itself.

**Solution:** Use the context manager properly:

```python
# Option 1: Synchronous approach (simpler for this use case)
from langgraph.checkpoint.postgres import PostgresSaver

# Get connection pool
import psycopg
conn = psycopg.connect(settings.database_url)

# Create checkpointer directly
_checkpointer_instance = PostgresSaver(conn)
_checkpointer_instance.setup()

# Option 2: Async context manager approach
async with PostgresSaver.from_conn_string(settings.database_url) as checkpointer:
    checkpointer.setup()
    _checkpointer_instance = checkpointer
```

**Impact:** This error prevents the entire email workflow from starting (affects 10/12 failed tests).

---

### Issue #2: AsyncMock Configuration Error

**Error:**
```
TypeError: '>' not supported between instances of 'AsyncMock' and 'int'
```

**Location:** `src/api/webhooks.py:101`

**Code:**
```python
stale_count = await db.get_stale_draft_count(thread_id)
if stale_count > 0:  # ❌ Fails in tests - stale_count is AsyncMock object
```

**Root Cause:** Test fixtures are not properly configuring the return value of `get_stale_draft_count()`.

**Solution:** Fix test fixture in `tests/conftest.py`:

```python
# In the database mock fixture:
mock_db.get_stale_draft_count.return_value = 0  # Must be integer, not AsyncMock
```

**Impact:** Affects 1 test (`test_trailing_email_in_existing_thread`).

---

### Issue #3: Test Authentication Logic

**Error:**
```
AssertionError: assert 'No pending drafts' in 'Unknown reviewer'
```

**Location:** `tests/integration/test_edge_cases.py:143`

**Root Cause:** The test expects "No pending drafts" error, but the code checks for unknown reviewer BEFORE checking for pending drafts.

**Code flow in `src/api/webhooks.py`:**
```python
# Line 217-219: Reviewer check happens FIRST
reviewer = await db.get_reviewer_by_phone(phone)
if not reviewer:
    return {"status": "error", "error": "Unknown reviewer"}

# Line 241+: Draft check happens AFTER
draft = await db.get_pending_draft_for_reviewer(reviewer_id)
if not draft:
    return {"status": "success", "message": "No pending drafts found"}
```

**Solution:** Update test to use a valid reviewer phone number:

```python
# In test fixture, add reviewer to database first:
await db.create_reviewer(phone_number="+1234567890", ...)

# OR use the test_reviewer fixture that already exists
```

**Impact:** Affects 1 test (`test_no_pending_drafts_scenario`).

---

## 📊 Coverage Report

**Current Coverage:** 40%
**Required Coverage:** 70%
**Gap:** -30%

**Uncovered Areas:**
- `src/api/webhooks.py`: 26% covered (86/117 lines missing)
- `src/services/database.py`: 35% covered (40/62 lines missing)
- `src/services/llm.py`: 19% covered (58/72 lines missing)
- `src/services/whatsapp.py`: 23% covered (41/53 lines missing)
- `src/workflows/graph.py`: 19% covered (91/112 lines missing)

**Note:** Coverage is low because:
1. Integration tests are failing due to the PostgresSaver error
2. Many workflow paths not executed due to early failures
3. Mock configuration issues prevent full flow execution

---

## 🛠️ Recommended Fixes

### Priority 1: Fix PostgresSaver Initialization (CRITICAL)

**File:** `src/workflows/graph.py:417-422`

**Current:**
```python
_checkpointer_instance = PostgresSaver.from_conn_string(
    settings.database_url
)
_checkpointer_instance.setup()
```

**Fixed:**
```python
import psycopg

# Create connection pool
conn = psycopg.connect(settings.database_url)

# Create checkpointer
_checkpointer_instance = PostgresSaver(conn)

# Setup tables (idempotent - safe to call multiple times)
_checkpointer_instance.setup()
```

**Expected Impact:** Fixes 10/12 failed tests.

---

### Priority 2: Fix Test Mock Configurations

**File:** `tests/conftest.py`

Add proper return values for async mocks:

```python
@pytest.fixture
def mock_database(mocker):
    mock = mocker.AsyncMock()

    # ✅ Add explicit return values for all async methods
    mock.get_stale_draft_count.return_value = 0  # Integer, not AsyncMock
    mock.get_pending_draft_for_reviewer.return_value = None
    mock.get_thread_by_id.return_value = {"id": "...", "status": "active"}

    # ... (configure all other methods)

    return mock
```

**Expected Impact:** Fixes 1-2 failed tests.

---

### Priority 3: Fix Test Data Setup

**File:** `tests/integration/test_edge_cases.py:143`

Ensure reviewer exists before testing "no pending drafts":

```python
async def test_no_pending_drafts_scenario(async_client, test_reviewer):
    # Use test_reviewer fixture instead of unknown phone number
    response = await async_client.post(
        "/webhooks/whatsapp",
        json={
            "From": test_reviewer["phone_number"],  # ✅ Use valid reviewer
            "Body": "APPROVE"
        }
    )

    data = response.json()
    assert "No pending drafts" in data["message"]  # Should work now
```

**Expected Impact:** Fixes 1 failed test.

---

## 📝 Environment Configuration Status

### ✅ Credentials Verified

All environment variables are properly configured in `.env`:

- ✅ **Supabase:** Database URL and service role key present
- ✅ **Anthropic:** API key present (starts with `sk-ant-`)
- ✅ **SendGrid:** API key present (starts with `SG.`)
- ✅ **Twilio:** Account SID and auth token present
- ✅ **WhatsApp:** Sandbox number configured
- ✅ **Email:** Intake and from addresses configured

**Note:** The integration test failures are NOT due to missing credentials. They're due to code bugs in the checkpointer setup and test mocking.

---

## 🎯 Next Steps

### Immediate (Required to proceed):

1. **Fix PostgresSaver initialization** (Priority 1)
   - Estimated time: 10 minutes
   - Impact: Fixes 10/12 failed tests

2. **Fix AsyncMock configurations** (Priority 2)
   - Estimated time: 15 minutes
   - Impact: Fixes 1-2 failed tests

3. **Update test data setup** (Priority 3)
   - Estimated time: 5 minutes
   - Impact: Fixes 1 failed test

**Total estimated fix time:** ~30 minutes
**Expected result after fixes:** 18-20/20 tests passing (90-100%)

### Follow-up (After fixes):

4. Run full test suite with coverage:
   ```bash
   pytest tests/ --cov=src --cov-report=html
   ```

5. Verify coverage reaches 70%+ threshold

6. Run manual end-to-end test from `TESTING.md`

---

## 🔍 Additional Observations

### Positive Signs:
- ✅ All unit tests passing (code quality is good)
- ✅ 40% of integration tests passing (core mocking works)
- ✅ No credential/authentication errors from external APIs
- ✅ Test infrastructure is well-designed (good fixtures, proper setup)

### Areas for Improvement:
- PostgresSaver usage needs correction (breaking most tests)
- Some mock return values need explicit configuration
- Test data fixtures need proper relationships (reviewer → drafts)

---

## 📌 Conclusion

**Status:** Tests partially working, with 1 critical blocker

**Blocker:** PostgresSaver context manager misuse preventing workflow execution

**Recommendation:** Fix Priority 1 issue first. This single fix will likely resolve 10/12 failed tests and unblock all testing.

**Your `.env` configuration is correct** - the failures are code bugs, not configuration issues.

---

**Would you like me to implement the Priority 1 fix to the PostgresSaver initialization?**
