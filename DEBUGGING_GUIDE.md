# Debugging Guide

## Logging System

Comprehensive logging has been added to help debug the "No jobs found" issue after `/more` command.

### Log Locations

1. **Console Output**: All logs are printed to stdout
2. **Log File**: `bot.log` in the project root directory (UTF-8 encoded)

### Log Levels

- **INFO**: Key operations and flow (user requests, API calls, results)
- **DEBUG**: Detailed information (individual job scoring, filtering decisions)
- **WARNING**: Issues that don't stop execution
- **ERROR**: Errors that prevent operations

### Key Log Tags

#### `[MORE]` - /more Command Flow
Tracks the entire flow when user requests more jobs:
```
[MORE] User {user_id} requested more jobs
[MORE] User {user_id} has {count} total keywords, {count} positive: [list]
[MORE] Searching by keywords: [list] / No keywords found, fetching recent jobs
[MORE] Fetched {count} jobs from Adzuna
[MORE] Ranking {count} jobs for user {user_id}
[MORE] After ranking and filtering, {count} jobs remain
[MORE] Sending {count} jobs to user {user_id}
[MORE] Job {n}/{total}: {job_id} - {title} - Score: {score}
```

#### `[ADZUNA]` - API Interactions
Tracks all Adzuna API calls:
```
[ADZUNA] search_by_keywords called with {count} keywords: [list], limit={n}
[ADZUNA] get_recent_jobs called with limit={n}, max_days_old={n}
[ADZUNA] Requesting jobs from {url}
[ADZUNA] Received {count} jobs from API (count in response: {total})
[ADZUNA] Error fetching jobs: {error}
```

#### `[RANK]` - Job Ranking Logic
Tracks job scoring and filtering:
```
[RANK] Starting to rank {count} jobs for user {user_id}
[RANK] User {user_id} has {count} keywords
[RANK] User {user_id} has {count} recently shown jobs (last 7 days)
[RANK] Excluding recently shown job: {job_id} - {title}
[RANK] Excluding job with negative score: {job_id} - {title} (score: {score}, matched: [list])
[RANK] Job {job_id} - {title} scored {score} (matched: [list])
[RANK] Results for user {user_id}: {count} jobs passed, {count} excluded (recent), {count} excluded (negative score)
[RANK] Top 5 scores: [(job_id, score), ...]
```

#### `[SCORE]` - Individual Job Scoring (DEBUG level)
Detailed scoring for each job:
```
[SCORE] Job {job_id} hard rejected due to negative keyword '{keyword}' (weight: {weight})
[SCORE] Job {job_id} soft negative '{keyword}' (weight: {weight}, new score: {score})
[SCORE] Job {job_id} positive match '{keyword}' (weight: {weight}, contribution: {contribution}, new score: {score})
[SCORE] Job {job_id} additional penalty for only negative matches (score: {score})
[SCORE] Job {job_id} title match bonus: {bonus} (final score: {score})
[SCORE] Job {job_id} final score: {score}, matched: [list]
```

## Common Issues and Solutions

### Issue: "No jobs found right now"

**Possible Causes:**
1. Adzuna API returned 0 jobs
   - Check `[ADZUNA] Received 0 jobs from API`
   - API might be down or keywords are too specific
   
2. All jobs filtered out as "recently shown"
   - Check `[RANK] Results for user {user_id}: 0 jobs passed, {high_number} excluded (recent)`
   - User has seen all available jobs in the last 7 days
   - Solution: Use `/search` or wait for new jobs

3. All jobs have negative scores
   - Check `[RANK] Results for user {user_id}: 0 jobs passed, 0 excluded (recent), {high_number} excluded (negative score)`
   - User's negative keywords are too broad
   - Solution: Review `/keywords` and like more jobs to balance profile

### Issue: "You've seen all recent matches"

This occurs when:
- Jobs are returned from Adzuna
- But all are filtered out during ranking (recently shown + negative scores)
- Check the ranking logs to see the breakdown

## How to Debug a User Issue

1. **Start the bot** with logging enabled (already configured)
2. **User triggers `/more` command**
3. **Check logs** for the flow:
   ```
   grep "User {user_id}" bot.log
   ```
4. **Identify the bottleneck**:
   - No jobs from API? → Check API credentials, network
   - All filtered as recent? → Jobs are being shown, user needs to wait
   - All negative scores? → User profile needs adjustment (like more jobs)

## Viewing Logs

### Real-time monitoring:
```bash
# PowerShell
Get-Content bot.log -Wait -Tail 50

# Or use tail in Git Bash
tail -f bot.log
```

### Filter by user:
```bash
# PowerShell
Select-String -Path bot.log -Pattern "User 123456789"

# Or grep
grep "User 123456789" bot.log
```

### Filter by specific issue:
```bash
# See all ranking results
grep "[RANK] Results" bot.log

# See all API responses
grep "[ADZUNA] Received" bot.log
```

## Debug Level Logging

To enable DEBUG level logging (very verbose, shows every job scoring):

Edit `main.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    ...
)
```

**Warning**: DEBUG logs are very verbose. Use only for deep investigation.
