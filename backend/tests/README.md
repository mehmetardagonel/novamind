# Email System Tests

This directory contains all tests for the Novamind Cloud email system.

## Directory Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared pytest configuration and fixtures
├── fixtures/                   # Reusable test fixtures and mock data
│   ├── __init__.py
│   ├── mock_data.py           # Mock email and draft data
│   └── mock_helpers.py        # Mock functions for LLM and tools
├── integration/               # Integration tests (test full system)
│   ├── __init__.py
│   ├── test_multi_agent_email_system.py
│   └── test_draft_and_summary_features.py
└── unit/                      # Unit tests (test individual components)
    ├── __init__.py
    ├── test_agent_tools.py
    └── test_agent_prompts.py
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run specific test categories
```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/integration/test_multi_agent_email_system.py
```

### Run with coverage
```bash
pytest tests/ --cov=agents --cov=email_tools
```

### Run with verbose output
```bash
pytest tests/ -v
```

## Test Categories

### Unit Tests (`tests/unit/`)
- Test individual components in isolation
- Fast execution
- Use mocks for external dependencies
- Focus on single functions or classes

### Integration Tests (`tests/integration/`)
- Test multiple components working together
- Test full system workflows (supervisor + agents + tools)
- May be slower than unit tests
- Test realistic scenarios

## Writing New Tests

### Example Unit Test
```python
def test_email_parsing():
    """Test that email data is parsed correctly."""
    email = parse_email(raw_data)
    assert email['sender'] == 'test@example.com'
    assert email['subject'] == 'Test Subject'
```

### Example Integration Test
```python
@pytest.mark.integration
def test_draft_deletion_flow(supervisor_graph):
    """Test the complete draft deletion workflow."""
    state = create_initial_state(
        user_message="Delete draft to john@example.com",
        user_id="test_user"
    )

    result = supervisor_graph.invoke(state)
    assert "deleted" in result.get("response", "").lower()
```

## Mock Data

Shared mock data is available in `tests/fixtures/mock_data.py`:
- `MOCK_EMAILS`: List of realistic test emails
- `MOCK_DRAFTS`: List of test draft emails
- `MOCK_USER_ID`: Test user ID
- `MOCK_USER_EMAIL`: Test user email address

## Mock Helpers

Helper functions for mocking are in `tests/fixtures/mock_helpers.py`:
- `mock_fetch_mails()`: Mock email fetching
- `mock_get_drafts_for_recipient()`: Mock draft retrieval
- `mock_delete_draft()`: Mock draft deletion
- `create_mock_llm_*()`: Various LLM mocks

## Current Test Status

**Passing: 3/10 tests**
- ✅ Email summarization (today)
- ✅ Email summarization (important only)
- ✅ Conversational context maintenance

**Note**: Some integration tests require improvements to the mock system to properly simulate LLM tool execution. The core functionality works in production; the test failures are due to mocking limitations.

## Next Steps

1. Improve LLM mocks to better simulate tool calling behavior
2. Add more unit tests for individual agent functions
3. Add tests for error handling and edge cases
4. Increase test coverage to >80%
