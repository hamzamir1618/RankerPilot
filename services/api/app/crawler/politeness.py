import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from app.core.rate_limit import redis_client

# Lua script to acquire both concurrency slot and respect 500ms delay
# KEYS[1]: concurrency set (ZSET of active request IDs with score = timestamp)
# KEYS[2]: last_request_time key
# ARGV[1]: current timestamp in ms
# ARGV[2]: request ID
# ARGV[3]: max concurrency (2)
# ARGV[4]: delay ms (500)
# ARGV[5]: expiration of concurrency key (timeout safety, e.g., 60000 ms)

ACQUIRE_SCRIPT = """
local curr_ms = tonumber(ARGV[1])
local req_id = ARGV[2]
local max_conn = tonumber(ARGV[3])
local delay_ms = tonumber(ARGV[4])
local expiry_ms = tonumber(ARGV[5])

-- Clean up dead locks from ZSET (older than expiry_ms)
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, curr_ms - expiry_ms)

-- Check concurrency
local active_count = redis.call('ZCARD', KEYS[1])
if active_count >= max_conn then
    return -1 -- Concurrency full
end

-- Check delay
local last_time = redis.call('GET', KEYS[2])
if last_time then
    local diff = curr_ms - tonumber(last_time)
    if diff < delay_ms then
        return delay_ms - diff -- Tell client to wait this many ms
    end
end

-- Acquire!
redis.call('ZADD', KEYS[1], curr_ms, req_id)
redis.call('PEXPIRE', KEYS[1], expiry_ms)
redis.call('SET', KEYS[2], curr_ms, 'PX', delay_ms)

return 0 -- Success
"""

RELEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
return 1
"""

@asynccontextmanager
async def politeness_lock(hostname: str, max_concurrency: int = 2, delay_ms: int = 500):
    """
    Ensures per-host concurrency and a delay between requests.
    """
    req_id = str(uuid.uuid4())
    concurrency_key = f"politeness:conn:{hostname}"
    last_req_key = f"politeness:last:{hostname}"
    
    # 60s max hold time to prevent deadlocks if process crashes
    expiry_ms = 60000 
    
    try:
        while True:
            curr_ms = int(time.time() * 1000)
            result = await redis_client.eval(
                ACQUIRE_SCRIPT, 
                2, 
                concurrency_key, 
                last_req_key, 
                curr_ms, 
                req_id, 
                max_concurrency, 
                delay_ms, 
                expiry_ms
            )
            
            if result == 0:
                # Acquired
                break
            elif result == -1:
                # Concurrency full, wait a bit and retry
                await asyncio.sleep(0.5)
            else:
                # Needs to wait for delay
                await asyncio.sleep(result / 1000.0)
                
        yield
        
    finally:
        await redis_client.eval(RELEASE_SCRIPT, 1, concurrency_key, req_id)
