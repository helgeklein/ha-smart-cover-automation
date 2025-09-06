# Testing Documentation for Smart Cover Automation

## Overview

This document describes the comprehensive test suite for the Smart Cover Automation integration, following Home Assistant and HACS best practices.

## Test Structure

### Test Files

- `tests/conftest.py` - Common fixtures and utilities
- `tests/test_coordinator.py` - DataUpdateCoordinator tests
- `tests/test_config_flow.py` - Configuration flow tests
- `tests/test_init.py` - Integration setup/teardown tests
- `tests/test_entity.py` - Entity base class tests
- `tests/test_integration.py` - End-to-end integration tests

### Test Coverage Areas

#### 1. Coordinator Tests (`test_coordinator.py`)
- **Temperature Automation**:
  - Hot weather scenarios (closing covers)
  - Cold weather scenarios (opening covers)
  - Comfortable temperature (maintaining position)
  - Temperature sensor error handling
  - Invalid temperature readings

- **Sun Automation**:
  - Direct sunlight scenarios
  - Low sun elevation behavior
  - Sun position calculations
  - Window azimuth handling
  - Sun entity error handling

- **Error Handling**:
  - Sensor not found errors
  - Invalid sensor readings
  - Service call failures
  - Entity unavailability
  - Configuration errors

- **Service Calls**:
  - Position-capable covers
  - Basic open/close covers
  - Service failure recovery

#### 2. Config Flow Tests (`test_config_flow.py`)
- **Successful Configuration**:
  - Temperature automation setup
  - Sun automation setup
  - Multiple cover selection
  - Unique ID generation

- **Validation Errors**:
  - Invalid cover entities
  - Invalid temperature ranges
  - Missing configuration fields
  - Unavailable covers (with warnings)

- **Form Handling**:
  - Initial form display
  - Error display and recovery
  - Input validation

#### 3. Integration Setup Tests (`test_init.py`)
- **Setup Process**:
  - Successful integration setup
  - Coordinator initialization
  - Platform setup
  - Runtime data configuration
  - Update listener setup

- **Error Scenarios**:
  - Coordinator initialization failures
  - Platform setup failures
  - Refresh failures

- **Teardown Process**:
  - Successful unload
  - Unload error handling
  - Reload functionality

#### 4. Entity Tests (`test_entity.py`)
- **Base Entity**:
  - Proper initialization
  - Device info setup
  - Unique ID generation
  - Coordinator reference

#### 5. Integration Tests (`test_integration.py`)
- **Complete Scenarios**:
  - Full temperature automation cycles
  - Daily sun automation cycles
  - Multiple cover coordination
  - Mixed cover capabilities

- **Error Recovery**:
  - Temporary sensor failures
  - Service call failures with continuation
  - Configuration validation

## Test Execution

### Running Tests

```bash
# Run all tests
./scripts/test

# Run specific test file
python3 -m pytest tests/test_coordinator.py -v

# Run with coverage
python3 -m pytest tests/ --cov=custom_components.smart_cover_automation --cov-report=html
```

### Test Requirements

Tests require the packages listed in `requirements-test.txt`.

## Test Best Practices

### 1. Mocking Strategy

- **HomeAssistant Core**: Mock `hass` instance with required services
- **Entity States**: Mock state objects with appropriate attributes
- **Service Calls**: Use `AsyncMock` for `hass.services.async_call`
- **Time-based**: Control time progression for automation testing

### 2. Fixtures Usage

- Reusable fixtures for common objects (hass, config entries, states)
- Parameterized fixtures for testing multiple scenarios
- Scoped fixtures to optimize test performance

### 3. Assertion Patterns

```python
# Test result structure
assert result is not None
assert "covers" in result
assert len(result["covers"]) > 0

# Test service calls
await assert_service_called(
    mock_services,
    "cover",
    "set_cover_position",
    "cover.test",
    position=50
)

# Test error handling
with pytest.raises(SensorNotFoundError) as exc_info:
    await coordinator._async_update_data()
assert "sensor.temperature" in str(exc_info.value)
```

### 4. Error Testing

Each error condition should be tested:
- Invalid inputs
- Missing entities
- Service failures
- Network timeouts
- Malformed data

### 5. Coverage Goals

Target coverage levels:
- **Overall**: >95%
- **Critical paths**: 100% (error handling, automation logic)
- **Configuration**: >90%
- **UI components**: >85%

## Test Data Management

### Mock Data

Tests use consistent mock data defined in `conftest.py`:
- `MOCK_COVER_ENTITY_ID` - Primary test cover
- `MOCK_COVER_ENTITY_ID_2` - Secondary test cover
- `MOCK_TEMP_SENSOR_ENTITY_ID` - Temperature sensor
- `MOCK_SUN_ENTITY_ID` - Sun entity

### Test Scenarios

Common scenarios are encapsulated in helper functions:
- `create_temperature_config()` - Temperature automation config
- `create_sun_config()` - Sun automation config
- `assert_service_called()` - Service call verification

## Integration with CI/CD

### GitHub Actions

Tests are integrated with GitHub Actions workflow:
```yaml
- name: Run tests
  run: |
    python -m pip install -r requirements-test.txt
    python -m pytest tests/ --cov=custom_components.smart_cover_automation
```

### Quality Gates

Tests serve as quality gates for:
- Pull request validation
- Release readiness
- Regression prevention
- Performance monitoring

## Debugging Tests

### Common Issues

1. **Async/Await Problems**:
   ```python
   # Correct async test pattern
   async def test_async_function():
       result = await async_function()
       assert result is not None
   ```

2. **Mock Side Effects**:
   ```python
   # Correct mock setup for multiple calls
   mock.side_effect = [value1, value2, value3]
   ```

3. **State Management**:
   ```python
   # Reset mocks between tests
   mock.reset_mock()
   ```

### Test Debugging Tools

- `pytest -v` - Verbose output
- `pytest -s` - Show print statements
- `pytest --pdb` - Drop into debugger on failure
- `pytest --tb=short` - Shorter tracebacks

## Future Test Enhancements

### Planned Additions

1. **Performance Tests**:
   - Automation response time
   - Memory usage monitoring
   - Concurrent operation testing

2. **Integration Tests**:
   - Real Home Assistant instance testing
   - Hardware-in-the-loop testing
   - End-to-end user workflows

3. **Property-Based Testing**:
   - Hypothesis-based input generation
   - Edge case discovery
   - Invariant verification

4. **Visual Testing**:
   - UI component testing
   - Configuration flow screenshots
   - Error message validation

### Continuous Improvement

- Regular review of test coverage reports
- Addition of tests for new features
- Refactoring of test utilities
- Performance optimization of test suite

## Conclusion

This comprehensive test suite ensures the Smart Cover Automation integration is reliable, maintainable, and follows Home Assistant best practices. The tests provide confidence in:

- Core automation logic
- Error handling and recovery
- Configuration validation
- Service integration
- User experience

Regular execution of these tests helps maintain code quality and prevents regressions as the integration evolves.
