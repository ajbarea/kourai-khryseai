# Testcontainers Cloud Setup Guide

This guide explains how to set up Testcontainers Cloud for running integration tests in cloud environments where Docker daemon is unavailable.

## Overview

**Testcontainers Cloud** allows integration tests that require containers to run in the cloud instead of locally. This is essential for:
- Cloud sandboxes (gVisor, Cloud Run, etc.)
- Kubernetes environments
- CI/CD pipelines without Docker daemon access
- Restricted security environments

## Quick Start

### 1. Get Your API Token

1. Go to [testcontainers.com/cloud](https://testcontainers.com/cloud/)
2. Sign up or log in to your account
3. Navigate to your dashboard
4. Generate a new API token (keep this secret!)

### 2. Add Token to `.env`

Copy `.env.example` to `.env` and add your token:

```bash
cp .env.example .env
```

Edit `.env` and uncomment/set:

```bash
# Testcontainers Cloud — Integration Testing in Cloud Environments
TESTCONTAINERS_CLOUD_TOKEN=your_token_here
TESTCONTAINERS_CLOUD_ENABLED=true
```

### 3. Run Integration Tests

```bash
make test-integration
```

Testcontainers will automatically:
- Detect `TESTCONTAINERS_CLOUD_TOKEN` from `.env`
- Route container requests to Testcontainers Cloud
- Run tests that would normally require Docker

## How It Works

1. **Environment Detection**: When integration tests start, testcontainers checks for:
   - `TESTCONTAINERS_CLOUD_TOKEN` environment variable
   - Local Docker daemon (fallback)

2. **Cloud Routing**: If cloud token is set, container lifecycle is managed in the cloud

3. **Graceful Degradation**: Our conftest Docker availability check ensures:
   - Tests requiring containers are skipped if unavailable
   - Other tests continue running normally
   - Clear skip messages in test output

## Configuration Files

### `.env` (Local - Keep Secret)
Your actual credentials (never commit to git):
```bash
TESTCONTAINERS_CLOUD_TOKEN=your_actual_token
TESTCONTAINERS_CLOUD_ENABLED=true
```

### `.env.example` (Repository - Template)
Template for new developers:
```bash
# TESTCONTAINERS_CLOUD_TOKEN=
# TESTCONTAINERS_CLOUD_ENABLED=true
```

### `.testcontainers.properties.example`
Optional: Properties file format (environment variables take precedence):
```properties
testcontainers.cloud.token=${TESTCONTAINERS_CLOUD_TOKEN}
testcontainers.cloud.enabled=true
```

## Environment Behavior

| Scenario | Behavior |
|----------|----------|
| Token set, Cloud enabled | Tests run in Testcontainers Cloud ✅ |
| Token set, Cloud disabled | Tests use local Docker if available |
| No token, Docker available | Tests use local Docker |
| No token, No Docker | Tests requiring containers are skipped ⏭️ |

## Troubleshooting

### "Docker daemon not available or misconfigured"
- This is expected if token isn't set and Docker isn't running
- Tests are gracefully skipped (see log output)
- Set `TESTCONTAINERS_CLOUD_TOKEN` to enable cloud testing

### Tests still trying to use local Docker
- Ensure `TESTCONTAINERS_CLOUD_TOKEN` is actually set:
  ```bash
  echo $TESTCONTAINERS_CLOUD_TOKEN
  ```
- Check that `.env` is loaded before running tests
- Verify token is valid in Testcontainers Cloud dashboard

### Token rejected by Testcontainers Cloud
- Verify token hasn't expired in dashboard
- Generate a new token and update `.env`
- Check for accidental whitespace in token value

## CI/CD Integration

For GitHub Actions or similar CI/CD:

1. Add secret to repository settings:
   - Name: `TESTCONTAINERS_CLOUD_TOKEN`
   - Value: Your actual token

2. Use in workflow:
   ```yaml
   - name: Run Integration Tests
     env:
       TESTCONTAINERS_CLOUD_TOKEN: ${{ secrets.TESTCONTAINERS_CLOUD_TOKEN }}
     run: make test-integration
   ```

## Security Notes

- **Never commit `.env`** to git (it's in `.gitignore`)
- **Never log the token** - testcontainers libraries mask it automatically
- **Rotate tokens regularly** in dashboard for security
- **Use limited scopes** when creating tokens (if supported)

## Next Steps

After setup:

1. Run: `make test-integration`
2. Check test output for skipped vs passed tests
3. Verify integration tests using containers are passing
4. Commit `.env.example` changes (credentials stay in `.env`)

## References

- [Testcontainers Cloud Documentation](https://testcontainers.com/cloud/)
- [Testcontainers Cloud vs Docker-in-Docker](https://www.docker.com/blog/testcontainers-cloud-vs-docker-in-docker-for-testing-scenarios/)
- [Kourai Khryseai Integration Tests](./tests/integration/)
