# CLAUDE.md - Kumon Assistant Instructions

## Database Connection Commands

### Railway PostgreSQL Production Database

**Connection Details:**
- Host: yamabiko.proxy.rlwy.net
- Port: 20931
- User: postgres
- Password: XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR
- Database: railway

**Base Command Pattern:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "YOUR_SQL_COMMAND"
```

### Common Database Operations

**List Tables:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "\dt"
```

**Describe Table Structure:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "\d conversation_sessions"
```

**Query Recent Conversations:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "SELECT session_id, phone_number, current_stage, current_step, updated_at FROM conversation_sessions ORDER BY updated_at DESC LIMIT 5;"
```

**Delete Conversation History:**
```bash
# Delete messages first
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "DELETE FROM conversation_messages WHERE conversation_id = 'SESSION_ID';"

# Then delete session
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "DELETE FROM conversation_sessions WHERE session_id = 'SESSION_ID';"
```

**Reset Conversation State:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "UPDATE conversation_sessions SET current_stage = 'greeting', current_step = 'initial_contact', status = 'active', updated_at = NOW(), ended_at = NULL WHERE session_id = 'SESSION_ID';"
```

### Database Schema

**Main Tables:**
- `conversation_sessions` - Session metadata and state
- `conversation_messages` - Individual messages 
- `user_profiles` - User profile information
- `daily_conversation_metrics` - Analytics data

**Key Fields in conversation_sessions:**
- `session_id` - Primary key
- `phone_number` - WhatsApp number
- `current_stage` - greeting, qualification, information_gathering, scheduling, completed
- `current_step` - Specific step within stage
- `status` - active, completed, ended
- `updated_at` - Last modification timestamp

---

*More instructions will be added here in the future*