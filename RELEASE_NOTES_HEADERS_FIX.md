# Release Notes - Headers Fix for Turn Guard Only Mode

## Version: 2.1.0
**Date:** December 2024  
**Type:** Security Enhancement / Bug Fix

## Summary
Fixed authentication blocking issue in Turn Guard Only mode where valid webhook requests were being rejected due to empty headers in internal calls. The fix implements a controlled fail-open mechanism for trusted sources while maintaining security for external requests.

## Problem Solved
- **Issue:** Pipeline was failing at preprocessing stage with `AUTH_FAILED` when Turn Guard Only mode was enabled
- **Root Cause:** Headers were not being properly propagated through internal function calls
- **Impact:** Messages were blocked before reaching the SmartRouter, preventing the entire pipeline from executing

## Changes Implemented

### 1. Feature Flag Addition
- **New Flag:** `ALLOW_EMPTY_HEADERS` (default: `false`)
- **Purpose:** Allow requests with empty headers when marked as `trusted_source=True`
- **Location:** `app/core/feature_flags.py`

### 2. Trusted Source Propagation
- Added `trusted_source: bool` parameter throughout the message processing chain:
  - `handle_messages_upsert_direct()` → marks webhook as trusted
  - `process_message_background()` → propagates trust flag
  - `_process_single_message()` → passes to preprocessor
  - `_process_through_turn_architecture()` → maintains trust context
  - `MessagePreprocessor.process_message()` → uses for auth validation

### 3. Authentication Validator Enhancement
- `AuthValidator.validate_request()` now accepts `trusted_source` parameter
- Logic: Empty headers + `trusted_source=True` + `ALLOW_EMPTY_HEADERS=true` → Allow
- Otherwise: Standard authentication validation applies

### 4. Enhanced Telemetry
- Added structured logging events:
  - `PREPROCESS|auth_ok` - Authentication successful
  - `PREPROCESS|auth_failed` - Authentication failed with reason
  - `PIPELINE|preprocess_start` - Now includes `trusted_source` flag
- Improved visibility into authentication flow

## Deployment Instructions

### Environment Variables
```bash
# Temporary - enable during transition period
export ALLOW_EMPTY_HEADERS=true

# After verifying headers are properly propagated
export ALLOW_EMPTY_HEADERS=false  # or remove the variable
```

### Rollout Strategy
1. **Stage 1:** Deploy with `ALLOW_EMPTY_HEADERS=true` to prevent blocking
2. **Stage 2:** Monitor logs for `auth_ok` events with `has_headers=false`
3. **Stage 3:** Fix header propagation at webhook level if needed
4. **Stage 4:** Disable flag once headers are consistently present

## Verification

### Expected Log Sequence (Successful Flow)
```
PIPELINE|preprocess_start|phone=9999|trusted_source=True
PREPROCESS|event=auth_ok|has_headers=True|trusted_source=True
PIPELINE|preprocess_complete|phone=9999
INTENT_CLASSIFIER|classify_complete|intent=greeting
SMART_ROUTER|decision=greeting_node
PLANNER|outbox_count=1
DELIVERY|turn_based_start
DELIVERY|sent|phone=9999
```

### Test Results
✅ Empty headers + `trusted_source=True` → **PASS**  
✅ Empty headers + `trusted_source=False` → **FAIL (Expected)**  
✅ Valid headers + any `trusted_source` → **PASS**

## Rollback Plan
If issues occur:
1. Set `ALLOW_EMPTY_HEADERS=false`
2. Revert commits if necessary
3. Headers will be strictly required again

## Files Modified
- `app/core/feature_flags.py` - Added `ALLOW_EMPTY_HEADERS` flag
- `app/api/evolution.py` - Propagated `trusted_source` through pipeline
- `app/services/message_preprocessor.py` - Enhanced auth validation logic
- `app/core/structured_logging.py` - (No changes needed, already supports kwargs)

## Security Considerations
- The fail-open mechanism ONLY applies when:
  1. Request comes from authenticated webhook endpoint (`trusted_source=True`)
  2. Feature flag is explicitly enabled (`ALLOW_EMPTY_HEADERS=true`)
- External requests without proper authentication are still blocked
- This is a temporary measure while header propagation is fixed at the source

## Monitoring
Monitor for:
- `PREPROCESS|auth_failed` events - Should decrease after deployment
- `auth_ok|has_headers=false` events - Indicates headers still missing
- Pipeline completion rate - Should increase significantly

## Success Metrics
- **Before:** Pipeline blocked at preprocessing with `AUTH_FAILED`
- **After:** Pipeline completes all stages (preprocess → classify → route → plan → outbox → delivery)
- **Target:** 100% of valid webhook messages processed successfully

---

**Note:** This is a defensive fix that maintains security while allowing the system to function. The long-term solution is to ensure headers are properly set at the webhook origin point.