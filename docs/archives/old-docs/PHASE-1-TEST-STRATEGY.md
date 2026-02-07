# Phase 1 Test Strategy
**Created:** February 4, 2026  
**Purpose:** Define testing approach after DEC-007 architecture refactor

---

## Why Tests Were Removed

**Date:** February 4, 2026  
**Reason:** Architecture-first approach

Previous tests were built on the **old adapter interface** (before DEC-007 compliance fix):
- ❌ Tested `adapter.check_anomaly()` - now removed (intelligence in QueryDispatcher)
- ❌ Tested `adapter.simulate_whatif()` - now removed (intelligence in QueryDispatcher)
- ❌ Tested direct adapter calls - should test through QueryDispatcher
- ❌ Written before architecture finalized - wrong assumptions

**Better to have NO tests than WRONG tests** that would mislead Emre.

---

## Current Test Status (Phase 0)

### ✅ Tests KEPT (Still Valid)

```
tests/
├── conftest.py                    # Shared fixtures & setup
├── requirements-test.txt          # pytest, pytest-asyncio dependencies
├── test_exceptions.py             # 15 exception types validated
├── test_result_types.py           # KPIResult, TrendResult, etc.
└── test_domain/
    └── test_models.py             # CanonicalMetric, TimePeriod, etc.
```

**Why kept:** Domain layer is correct, exceptions are correct, test infrastructure is correct.

### ❌ Tests REMOVED (Built on Wrong Architecture)

- `test_adapter_factory.py` - dummy adapters had old interface methods
- `test_query_dispatcher.py` - tested adapter calls, not orchestration
- `test_settings_service.py` - premature (DB layer not finalized)
- `test_skill_handlers.py` - OVOS integration not yet implemented
- `test_adapters/test_mock_adapter.py` - tested check_anomaly/simulate_whatif

---

## Phase 1 Test Writing Plan (M1-M2)

### Week 1: Adapter Tests (Emre writes, You review)

#### File: `tests/test_adapters/test_mock_adapter.py`

**What to test:**
```python
import pytest
from skill.adapters.mock import MockAdapter
from skill.domain.models import CanonicalMetric, TimePeriod

class TestMockAdapter:
    """Test MockAdapter provides correct data."""
    
    @pytest.fixture
    def adapter(self):
        return MockAdapter()
    
    # Query Type 1: KPI Retrieval
    async def test_get_kpi_returns_kpi_result(self, adapter):
        result = await adapter.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.OEE
        assert 0 <= result.value <= 100  # OEE is percentage
    
    # Query Type 2: Comparison
    async def test_compare_ranks_assets(self, adapter):
        result = await adapter.compare(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_ids=["Line-1", "Line-2", "Line-3"],
            period=TimePeriod.this_week()
        )
        assert len(result.items) == 3
        assert result.items[0].rank == 1  # Winner
        assert result.items[-1].rank == 3  # Loser
    
    # Query Type 3: Trend
    async def test_get_trend_has_data_points(self, adapter):
        result = await adapter.get_trend(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id="Line-1",
            period=TimePeriod.last_week(),
            granularity="daily"
        )
        assert len(result.data_points) >= 3
        assert result.direction in ["up", "down", "stable"]
    
    # Query Type 4: Raw Data (NEW - DEC-007 compliant)
    async def test_get_raw_data_returns_datapoints(self, adapter):
        result = await adapter.get_raw_data(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Line-1",
            period=TimePeriod.last_7_days()
        )
        assert len(result) >= 24  # At least 1 day of hourly data
        assert all(isinstance(dp, DataPoint) for dp in result)
        assert all(hasattr(dp, 'timestamp') for dp in result)
        assert all(hasattr(dp, 'value') for dp in result)
    
    # NO tests for check_anomaly() or simulate_whatif() - NOT in interface!
```

**Acceptance criteria:**
- All 4 query types tested (get_kpi, compare, get_trend, get_raw_data)
- Tests use actual domain types (not dicts)
- Assertions validate result structure AND data quality
- NO tests for intelligence methods (removed from adapter)

---

#### File: `tests/test_adapters/test_reneryo_adapter.py`

**When:** After You implement RENERYOAdapter (Week 2-3)

**What to test:**
```python
import pytest
import responses  # Mock HTTP requests
from skill.adapters.reneryo import RENERYOAdapter

class TestRENERYOAdapter:
    """Test RENERYO adapter transforms API responses correctly."""
    
    @pytest.fixture
    def adapter(self):
        return RENERYOAdapter(
            api_url="https://api.reneryo.com",
            api_key="test-key-123"
        )
    
    @responses.activate
    async def test_get_kpi_transforms_reneryo_response(self, adapter):
        # Mock RENERYO API response
        responses.add(
            responses.GET,
            "https://api.reneryo.com/v1/kpi",
            json={"seu_value": 2.85, "unit": "kWh/unit", "timestamp": "2026-02-04T10:00:00Z"},
            status=200
        )
        
        result = await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
        
        # Verify transformation to canonical type
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert result.value == 2.85
        assert result.unit == "kWh/unit"
    
    @responses.activate
    async def test_handles_api_failure_gracefully(self, adapter):
        responses.add(
            responses.GET,
            "https://api.reneryo.com/v1/kpi",
            status=500
        )
        
        with pytest.raises(AdapterError) as exc:
            await adapter.get_kpi(...)
        
        assert "RENERYO API unavailable" in str(exc.value)
```

**Acceptance criteria:**
- Mock RENERYO API responses (use `responses` library)
- Test successful data transformation
- Test error handling (401, 404, 500, timeout)
- Test retry logic if implemented

---

### Week 2: Orchestration Tests (You write, Emre observes)

#### File: `tests/test_services/test_query_dispatcher.py`

**What to test:**
```python
import pytest
from skill.use_cases.query_dispatcher import QueryDispatcher
from skill.adapters.mock import MockAdapter

class TestQueryDispatcher:
    """Test QueryDispatcher routes queries correctly."""
    
    @pytest.fixture
    def dispatcher(self):
        adapter = MockAdapter()
        return QueryDispatcher(adapter)
    
    def test_get_kpi_routes_to_adapter(self, dispatcher):
        result = dispatcher.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
        assert isinstance(result, KPIResult)
    
    def test_logs_audit_trail(self, dispatcher, mocker):
        # Mock audit logger
        mock_audit = mocker.patch.object(dispatcher._audit_logger, 'log_query')
        
        dispatcher.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
        
        # Verify audit log called
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args['query_type'] == 'get_kpi'
        assert call_args['metric'] == 'oee'
    
    # Phase 3: Test intelligence orchestration
    # def test_check_anomaly_orchestrates_prevention(self, dispatcher):
    #     """TODO PHASE 3: Test PREVENTION service integration"""
    #     pass
```

**Acceptance criteria:**
- Test query routing for 3 basic types (KPI, comparison, trend)
- Test audit logging on all queries
- Test adapter hot-swap (set_adapter)
- Phase 3: Add orchestration tests for check_anomaly/simulate_whatif

---

### Week 3: Integration Tests (Pair programming - You + Emre)

#### File: `tests/test_integration/test_end_to_end.py`

**What to test:**
```python
import pytest
from skill import AVAROSSkill  # Your OVOS skill class

class TestEndToEnd:
    """Test full intent → dispatcher → adapter → response flow."""
    
    @pytest.fixture
    def skill(self):
        return AVAROSSkill()
    
    def test_kpi_energy_intent_returns_dialog(self, skill):
        # Simulate user saying: "What's our energy per unit?"
        message = MockMessage(
            data={
                "metric": "energy_per_unit",
                "period": "today"
            }
        )
        
        result = skill.handle_kpi_energy(message)
        
        # Verify dialog response
        assert "kWh" in result
        assert "per unit" in result
    
    def test_adapter_failure_graceful_degradation(self, skill, mocker):
        # Mock adapter failure
        mocker.patch.object(
            skill.dispatcher.adapter,
            'get_kpi',
            side_effect=AdapterError("API timeout")
        )
        
        result = skill.handle_kpi_energy(message)
        
        # Should return error dialog, not crash
        assert "unable to retrieve" in result.lower()
```

**Acceptance criteria:**
- Test all 15 intents end-to-end
- Test error handling (adapter failure)
- Test dialog selection (correct .dialog file used)
- Test slot extraction (dates, assets, metrics)

---

### Week 4: Web UI Tests (Emre writes)

#### File: `tests/test_web/test_api_endpoints.py`

**What to test:**
```python
import pytest
from fastapi.testclient import TestClient
from skill.web.app import app

class TestAPIEndpoints:
    """Test FastAPI Web UI backend."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_get_kpi_endpoint(self, client):
        response = client.get(
            "/api/v1/kpi",
            params={
                "metric": "oee",
                "asset_id": "Line-1",
                "period": "today"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metric"] == "oee"
        assert "value" in data
    
    def test_settings_crud(self, client):
        # Create
        response = client.post(
            "/api/v1/settings",
            json={"platform": "reneryo", "api_url": "https://api.reneryo.com"}
        )
        assert response.status_code == 201
        
        # Read
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        
        # Update
        response = client.put(
            "/api/v1/settings",
            json={"platform": "reneryo", "api_url": "https://new.api.reneryo.com"}
        )
        assert response.status_code == 200
```

---

## Test-Driven Development Workflow

### Emre's PR Checklist
Before submitting PR, Emre must:
1. ✅ Write test FIRST (before implementation)
2. ✅ Test fails initially (red)
3. ✅ Implement feature
4. ✅ Test passes (green)
5. ✅ Run ALL tests (`pytest tests/ -v`)
6. ✅ Coverage >70% for new code

### Your Review Checklist
When reviewing Emre's PR:
1. ✅ Tests exist for new feature
2. ✅ Tests use actual domain types (not dicts/mocks)
3. ✅ Tests validate data quality (not just "returns result")
4. ✅ Edge cases covered (empty data, API failure)
5. ✅ Tests pass on your machine
6. ✅ No architectural violations (e.g., adapter doing intelligence)

---

## Coverage Targets

| Phase | Target | Components |
|-------|--------|------------|
| Phase 1 (M2) | 70% | Domain, adapters, dispatcher |
| Phase 2 (M3) | 80% | + Web UI, intent handlers |
| Phase 3 (M4) | 85% | + DocuBoT/PREVENTION orchestration |

Run coverage: `pytest --cov=skill --cov-report=html tests/`

---

## Testing Tools

**Installed (requirements-test.txt):**
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities
- `pytest-cov` - Coverage reporting

**To Add in Phase 1:**
- `responses` - Mock HTTP requests (for RENERYO adapter tests)
- `fastapi[test]` - FastAPI test client (for Web UI tests)
- `playwright` - E2E browser tests (Phase 2)

---

## Success Metrics (End of Phase 1)

- [ ] 30+ tests written
- [ ] MockAdapter: 100% coverage
- [ ] RENERYOAdapter: 80% coverage
- [ ] QueryDispatcher: 90% coverage
- [ ] All 15 intents have end-to-end tests
- [ ] Web UI: 70% API endpoint coverage
- [ ] Emre can write tests independently
- [ ] You trust Emre's test quality (fewer review comments per PR)

---

**Next:** Once Phase 0 complete, create GitHub issues for test tasks above.
