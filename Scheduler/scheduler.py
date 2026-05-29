import asyncio
import random
import time
import json
import sys
import os
import signal
from datetime import datetime
import httpx
from config import settings
from prometheus_client import start_http_server, Counter, Histogram, Gauge

# Metrics definition for Prometheus scraping
PING_TOTAL = Counter("keep_warm_pings_total", "Total keep-warm pings executed", ["url", "status"])
PING_LATENCY = Histogram("keep_warm_ping_latency_seconds", "Keep-warm ping latency in seconds", ["url"])
CONSECUTIVE_FAILURES = Gauge("keep_warm_consecutive_failures", "Number of consecutive ping failures", ["url"])
CIRCUIT_STATE = Gauge("keep_warm_circuit_state", "Circuit breaker state (0=closed, 1=open, 2=half_open)", ["url"])

# Track state of each backend URL's circuit breaker
circuit_states = {
    url: {
        "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
        "cooldown_until": 0.0,
        "failures": 0
    }
    for url in settings.BACKEND_URLS
}

# Helper to update circuit state gauge metric
def update_circuit_state_metric(url: str, state: str):
    state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
    CIRCUIT_STATE.labels(url=url).set(state_map.get(state, 0))

# JSON structured logging helper
def log_event(level: str, event: str, target: str = None, status_code: int = None, latency_ms: float = None, consecutive_failures: int = None, message: str = ""):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "event": event,
        "target": target,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "consecutive_failures": consecutive_failures,
        "message": message
    }
    cleaned_entry = {k: v for k, v in log_entry.items() if v is not None}
    print(json.dumps(cleaned_entry), flush=True)

# Webhook Alerting logic
async def trigger_webhook_alert(target_url: str, consecutive_failures: int, last_error: str):
    if not settings.ALERT_WEBHOOK_URL:
        return
        
    payload = {
        "text": f"🚨 [Keep-Warm Alert] Target backend {target_url} is down!",
        "attachments": [{
            "color": "danger",
            "fields": [
                {"title": "Target URL", "value": target_url, "short": True},
                {"title": "Consecutive Failures", "value": str(consecutive_failures), "short": True},
                {"title": "Last Error Details", "value": last_error, "short": False},
                {"title": "Timestamp", "value": datetime.utcnow().isoformat() + "Z", "short": False}
            ]
        }]
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(settings.ALERT_WEBHOOK_URL, json=payload)
            if r.status_code in (200, 204):
                log_event("info", "alert_webhook_sent", message=f"Webhook alert dispatched for {target_url}")
            else:
                log_event("error", "alert_webhook_failed", message=f"Webhook responded with {r.status_code}: {r.text}")
    except Exception as e:
        log_event("error", "alert_webhook_failed", message=f"Failed to post to alert webhook: {str(e)}")

# Core keep-alive single endpoint ping logic (with timeout, retry backoff, and circuit breaker)
async def ping_url(client: httpx.AsyncClient, url: str):
    state_info = circuit_states[url]
    current_time = time.time()
    
    # Evaluate circuit state
    if state_info["state"] == "OPEN":
        if current_time >= state_info["cooldown_until"]:
            state_info["state"] = "HALF_OPEN"
            update_circuit_state_metric(url, "HALF_OPEN")
            log_event("info", "circuit_half_open", target=url, message="Circuit breaker cooldown expired. Probing target recovery.")
        else:
            remaining = round(state_info["cooldown_until"] - current_time, 1)
            log_event("warning", "ping_skipped", target=url, message=f"Circuit is OPEN. Ping skipped. Cooldown remaining: {remaining}s")
            return

    headers = {"User-Agent": "KeepWarmScheduler/1.0.0"}
    if settings.KEEP_WARM_TOKEN:
        headers["X-Keep-Warm-Token"] = settings.KEEP_WARM_TOKEN

    last_error_details = ""
    is_half_open = (state_info["state"] == "HALF_OPEN")
    attempts_limit = 1 if is_half_open else settings.MAX_RETRIES
    
    for attempt in range(1, attempts_limit + 1):
        start_time = time.time()
        try:
            r = await client.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT_SEC)
            latency = round((time.time() - start_time) * 1000, 2)
            latency_sec = latency / 1000.0
            
            if r.status_code == 200:
                PING_TOTAL.labels(url=url, status="success").inc()
                PING_LATENCY.labels(url=url).observe(latency_sec)
                
                # Reset breaker metrics
                state_info["state"] = "CLOSED"
                state_info["failures"] = 0
                update_circuit_state_metric(url, "CLOSED")
                CONSECUTIVE_FAILURES.labels(url=url).set(0)
                
                log_event("info", "ping_success", target=url, status_code=200, latency_ms=latency)
                return
            else:
                last_error_details = f"HTTP {r.status_code}"
                PING_TOTAL.labels(url=url, status="unhealthy").inc()
                log_event("warning", "ping_unhealthy", target=url, status_code=r.status_code, latency_ms=latency, message=f"Attempt {attempt} returned non-200")
        except httpx.RequestError as e:
            latency = round((time.time() - start_time) * 1000, 2)
            last_error_details = str(e)
            PING_TOTAL.labels(url=url, status="error").inc()
            log_event("warning", "ping_error", target=url, latency_ms=latency, message=f"Attempt {attempt} failed connection: {str(e)}")
            
        # Exponential backoff sleep before next retry
        if attempt < attempts_limit:
            sleep_time = (settings.BACKOFF_FACTOR ** attempt) + random.uniform(0.1, 0.9)
            log_event("info", "backoff_retry", target=url, message=f"Sleeping {round(sleep_time, 2)}s before retry attempt {attempt + 1}")
            await asyncio.sleep(sleep_time)

    # Ping cycle failed for this target
    state_info["failures"] += 1
    failures = state_info["failures"]
    CONSECUTIVE_FAILURES.labels(url=url).set(failures)
    
    log_event("error", "ping_failed_all_attempts", target=url, consecutive_failures=failures, message=f"All ping attempts failed for {url}")
    
    # Trip circuit breaker if consecutive failures exceed threshold
    if failures >= settings.CONSECUTIVE_FAILURE_ALERT_THRESHOLD:
        state_info["state"] = "OPEN"
        state_info["cooldown_until"] = time.time() + settings.CIRCUIT_BREAKER_COOLDOWN_MIN * 60
        update_circuit_state_metric(url, "OPEN")
        
        log_event("critical", "circuit_tripped", target=url, consecutive_failures=failures, message=f"Circuit tripped to OPEN. Cooldown for {settings.CIRCUIT_BREAKER_COOLDOWN_MIN} mins.")
        await trigger_webhook_alert(url, failures, last_error_details)

# External Heartbeat Fallback
async def ping_external_heartbeat(client: httpx.AsyncClient):
    try:
        r = await client.get(settings.HEARTBEAT_URL, timeout=5.0)
        log_event("info", "heartbeat_success", target=settings.HEARTBEAT_URL, status_code=r.status_code, message="External heartbeat monitor pinged successfully.")
    except Exception as e:
        log_event("warning", "heartbeat_failed", target=settings.HEARTBEAT_URL, message=f"Failed to ping external heartbeat: {str(e)}")

# Keep-warm loop orchestrator
async def keep_warm_loop():
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits) as client:
        log_event("info", "scheduler_loop_started", message=f"Scheduler initialized. Pinging targets: {settings.BACKEND_URLS}")
        
        # Initialize default metrics states
        for url in settings.BACKEND_URLS:
            update_circuit_state_metric(url, "CLOSED")
            CONSECUTIVE_FAILURES.labels(url=url).set(0)

        while True:
            interval_minutes = random.uniform(settings.PING_INTERVAL_MIN, settings.PING_INTERVAL_MAX)
            interval_seconds = int(interval_minutes * 60)
            
            log_event("info", "ping_cycle_scheduled", message=f"Next ping cycle scheduled in {round(interval_minutes, 2)} minutes ({interval_seconds}s)")
            await asyncio.sleep(interval_seconds)
            
            log_event("info", "ping_cycle_started")
            tasks = [ping_url(client, url) for url in settings.BACKEND_URLS]
            await asyncio.gather(*tasks, return_exceptions=True)
            log_event("info", "ping_cycle_completed")
            
            if settings.HEARTBEAT_URL:
                await ping_external_heartbeat(client)

# Redis lock client and background lease renewal task
redis_client = None

async def renew_redis_lock(redis_url: str):
    global redis_client
    import redis
    redis_client = redis.from_url(redis_url)
    lock_key = "keep_warm_singleton_lock"
    pid = str(os.getpid())
    
    # Try to set key exclusively with a 60-second expiration
    acquired = redis_client.set(lock_key, pid, nx=True, ex=60)
    if not acquired:
        current_val = redis_client.get(lock_key)
        if current_val and current_val.decode('utf-8') == pid:
            acquired = True
            
    if not acquired:
        print(f"[{datetime.utcnow().isoformat()}] CRITICAL: Another scheduler instance holds the Redis distributed lock. Exiting.", flush=True)
        os._exit(0)
        
    log_event("info", "redis_lock_acquired", message="Redis distributed lock acquired.")
    
    # Keep lock lease active by renewing TTL every 30 seconds
    while True:
        await asyncio.sleep(30)
        try:
            val = redis_client.get(lock_key)
            if val and val.decode('utf-8') == pid:
                redis_client.expire(lock_key, 60)
            else:
                log_event("critical", "redis_lock_lost", message="Redis distributed lock was hijacked or lost. Exiting.")
                os._exit(0)
        except Exception as e:
            log_event("error", "redis_lock_renew_failed", message=f"Failed to renew Redis distributed lock: {str(e)}")

def release_redis_lock():
    global redis_client
    if redis_client:
        try:
            lock_key = "keep_warm_singleton_lock"
            pid = str(os.getpid())
            val = redis_client.get(lock_key)
            if val and val.decode('utf-8') == pid:
                redis_client.delete(lock_key)
                log_event("info", "redis_lock_released", message="Redis lock released successfully.")
        except Exception as e:
            print(f"Failed to release Redis lock: {e}", flush=True)

# Local filesystem locking strategy fallback
local_lock_file = None

def acquire_local_lock(lock_path: str = "keep_warm.lock"):
    global local_lock_file
    try:
        if os.name != 'nt':
            import fcntl
            local_lock_file = open(lock_path, 'w')
            fcntl.flock(local_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            local_lock_file.write(str(os.getpid()))
            local_lock_file.flush()
            return local_lock_file
        else:
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except Exception:
                    print(f"[{datetime.utcnow().isoformat()}] CRITICAL: Another scheduler instance is already running (file locked).", flush=True)
                    sys.exit(0)
            local_lock_file = open(lock_path, 'w')
            local_lock_file.write(str(os.getpid()))
            local_lock_file.flush()
            return local_lock_file
    except IOError:
        print(f"[{datetime.utcnow().isoformat()}] CRITICAL: Duplicate execution detected. Process exiting.", flush=True)
        sys.exit(0)

def release_local_lock(lock_path: str = "keep_warm.lock"):
    global local_lock_file
    if local_lock_file:
        try:
            local_lock_file.close()
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass

# Graceful termination handler
def shutdown_handler(signum, frame):
    log_event("info", "scheduler_shutting_down", message=f"Received signal {signum}. Cleared locks, exiting gracefully.")
    if settings.REDIS_URL:
        release_redis_lock()
    else:
        release_local_lock()
    sys.exit(0)

async def main_async():
    # Lease management
    if settings.REDIS_URL:
        asyncio.create_task(renew_redis_lock(settings.REDIS_URL))
    else:
        acquire_local_lock()

    # Start Prometheus server
    try:
        start_http_server(settings.METRICS_PORT)
        log_event("info", "metrics_server_started", message=f"Prometheus metrics exporter running on port {settings.METRICS_PORT}")
    except Exception as e:
        log_event("error", "metrics_server_failed", message=f"Failed to start Prometheus metrics exporter: {str(e)}")

    await keep_warm_loop()

def main():
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        asyncio.run(main_async())
    finally:
        if settings.REDIS_URL:
            release_redis_lock()
        else:
            release_local_lock()

if __name__ == "__main__":
    main()
